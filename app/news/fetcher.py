"""Fetch RSS feeds from all enabled news sources and store new articles.

Ported from ChattNews. feedparser is synchronous, so the network fetch + parse
runs in a thread; row upserts go through the async session. Hard-won feed
behavior that must not regress:
  * requests send a real-browser User-Agent (registry.USER_AGENT) — TownNews
    sites answer unfamiliar UAs with HTTP 429;
  * a feed erroring must never abort the cycle — failures are caught per-feed
    and recorded in news_feeds.last_status;
  * dedup is (source_id, guid); the category is content-derived (classify.py)
    and recomputed on every fetch, so an upsert overwrites it rather than
    one-way upgrading a generic 'news' category to a section.
"""

from __future__ import annotations

import asyncio
import calendar
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import feedparser
import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.news.classify import classify
from app.news.models import NewsArticle, NewsFeed, NewsSource
from app.news.registry import USER_AGENT, feed_kind, uses_feed_tags
from app.news.textutil import strip_html, truncate_sentences

log = logging.getLogger("localdash.news.fetcher")


def _entry_published(entry) -> datetime:
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            ts = calendar.timegm(parsed)
            return datetime.fromtimestamp(ts, tz=timezone.utc)
    return datetime.now(timezone.utc)


def _entry_summary(entry) -> str:
    raw = ""
    if getattr(entry, "content", None):
        raw = entry.content[0].get("value", "")
    if not raw:
        raw = getattr(entry, "summary", "") or getattr(entry, "description", "")
    return truncate_sentences(strip_html(raw), 600)


_IMG_SRC = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)


def _entry_image(entry) -> str | None:
    """Feed-supplied image URL: first image enclosure, else first inline <img>.

    Only reads what the feed already carries — no article page is fetched.
    Local 3 (TownNews) ships an image enclosure on most items; WDEF sometimes
    embeds an <img> in the item content; the other outlets carry neither.
    """
    for enc in getattr(entry, "enclosures", []) or []:
        if str(enc.get("type", "")).startswith("image") and enc.get("href"):
            return enc["href"]
    raw = ""
    if getattr(entry, "content", None):
        raw = entry.content[0].get("value", "")
    if not raw:
        raw = getattr(entry, "summary", "") or getattr(entry, "description", "")
    match = _IMG_SRC.search(raw or "")
    return match.group(1) if match else None


def _entry_tags(entry) -> list[str]:
    """Per-item feed <category> terms (WordPress outlets carry these; others
    don't). feedparser exposes them as entry.tags, each a dict with a 'term'."""
    return [t.get("term", "") for t in getattr(entry, "tags", []) or [] if t.get("term")]


def _parse_feed(url: str):
    return feedparser.parse(
        url,
        agent=USER_AGENT,
        request_headers={"Accept": "application/rss+xml, application/xml, */*"},
    )


def _row_published(row) -> datetime:
    """Published time from a scraped .views-row's <time datetime>, in UTC.

    The datetime attribute carries a tz offset (e.g. -04:00); fall back to now
    when it is absent or unparseable, mirroring _entry_published for RSS items.
    """
    node = row.select_one(".views-field-created time[datetime]")
    if node:
        try:
            return datetime.fromisoformat(node["datetime"]).astimezone(timezone.utc)
        except ValueError, KeyError:
            pass
    return datetime.now(timezone.utc)


def parse_html_listing(html: str, base_url: str) -> list[dict]:
    """Parse a Drupal View listing page into partial article rows (pure, offline).

    One `div.views-row` becomes one row dict with the same fields the RSS path
    builds, minus what the fetcher fills later (source_id, category, fetched_at):
    title + absolute URL, HTML-stripped/truncated summary, UTC published time,
    guid = the article URL, and image_url = None (the listing carries no image
    and no article page is fetched). Rows missing a title or link are skipped,
    mirroring the RSS loop; an unrecognized page yields [].
    """
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for row in soup.select("div.views-row"):
        link = row.select_one(".views-field-title h3 a[href]")
        if link is None:
            continue
        url = urljoin(base_url, link["href"].strip())
        title = strip_html(link.get_text())
        if not url or not title:
            continue
        body = row.select_one(".views-field-body .field-content")
        summary = truncate_sentences(strip_html(body.get_text()) if body else "", 600)
        rows.append(
            {
                "guid": url,
                "url": url,
                "title": title,
                "summary": summary,
                "image_url": None,
                "published": _row_published(row),
            }
        )
    return rows


async def _fetch_html(url: str) -> str:
    """GET a listing page with the shared browser User-Agent. Raises on non-2xx."""
    async with httpx.AsyncClient(
        timeout=30, follow_redirects=True, headers={"User-Agent": USER_AGENT}
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text


async def upsert_articles(session: AsyncSession, rows: list[dict]) -> int:
    """Insert article rows, deduplicating on (source_id, guid).

    Returns the affected-row count (inserts plus conflicting rows). The category
    is content-derived and recomputed each fetch, so a conflict overwrites the
    stored category with the freshly classified one (either direction).
    """
    if not rows:
        return 0
    # First occurrence wins on duplicate guids within one payload — a
    # multi-row INSERT can't touch the same conflict target twice.
    unique: dict[tuple, dict] = {}
    for row in rows:
        unique.setdefault((row["source_id"], row["guid"]), row)

    stmt = pg_insert(NewsArticle).values(list(unique.values()))
    stmt = stmt.on_conflict_do_update(
        constraint="uq_news_article_source_guid",
        set_={"category": stmt.excluded.category},
    )
    result = await session.execute(stmt)
    return result.rowcount


async def _fetch_html_feed(
    session: AsyncSession, feed: NewsFeed, source_slug: str
) -> tuple[int, str]:
    """Fetch one kind='html' feed by scraping its listing page. Returns
    (changed article count, status). An HTTP error propagates to fetch_all's
    per-feed handler; an empty/unrecognized page reports 'no entries'."""
    html = await _fetch_html(feed.url)
    partial = parse_html_listing(html, feed.url)
    if not partial:
        return 0, "error (no entries)"

    now = datetime.now(timezone.utc)
    rows = [
        {
            "source_id": feed.source_id,
            "guid": row["guid"],
            "url": row["url"],
            "title": row["title"],
            "summary": row["summary"],
            "image_url": row["image_url"],
            # No feed <category> tags on a scraped page, so the tag tier is a
            # no-op ([]); category is keyword-classified, else the feed section.
            "category": classify(row["title"], row["summary"], [], feed.category),
            "published": row["published"],
            "fetched_at": now,
        }
        for row in partial
    ]
    added = await upsert_articles(session, rows)
    return added, f"ok ({len(partial)} entries, {added} changed)"


async def fetch_feed(session: AsyncSession, feed: NewsFeed, source_slug: str) -> tuple[int, str]:
    """Fetch one feed. Returns (changed article count, status)."""
    if feed_kind(feed.url) == "html":
        return await _fetch_html_feed(session, feed, source_slug)

    parsed = await asyncio.to_thread(_parse_feed, feed.url)
    status = getattr(parsed, "status", None)
    if not parsed.entries:
        detail = f"http {status}" if status else "no entries"
        if parsed.bozo and getattr(parsed, "bozo_exception", None):
            detail = f"{detail}: {parsed.bozo_exception}"
        return 0, f"error ({detail})"

    now = datetime.now(timezone.utc)
    rows = []
    for entry in parsed.entries:
        url = getattr(entry, "link", "") or ""
        title = strip_html(getattr(entry, "title", "") or "")
        if not url or not title:
            continue
        summary = _entry_summary(entry)
        rows.append(
            {
                "source_id": feed.source_id,
                "guid": getattr(entry, "id", "") or url,
                "url": url,
                "title": title,
                "summary": summary,
                "image_url": _entry_image(entry),
                # Content-derived, not the feed section (feed.category is the
                # last-resort fallback inside classify()). Sources registered
                # with use_feed_tags: False carry only boilerplate tags, so the
                # tag tier is suppressed for them.
                "category": classify(
                    title,
                    summary,
                    _entry_tags(entry) if uses_feed_tags(source_slug) else [],
                    feed.category,
                ),
                "published": _entry_published(entry),
                "fetched_at": now,
            }
        )

    added = await upsert_articles(session, rows)
    return added, f"ok ({len(parsed.entries)} entries, {added} changed)"


async def fetch_all(session: AsyncSession) -> dict:
    """Fetch every feed of every enabled source. Returns {feed label: status}."""
    results = {}
    feeds = (
        await session.execute(
            select(NewsFeed, NewsSource.slug)
            .join(NewsSource, NewsSource.id == NewsFeed.source_id)
            .where(NewsSource.enabled.is_(True))
            .order_by(NewsFeed.source_id, NewsFeed.position)
        )
    ).all()
    for feed, source_slug in feeds:
        label = f"{source_slug}/{feed.category}"
        try:
            _, status = await fetch_feed(session, feed, source_slug)
        except Exception as exc:  # a broken feed must not kill the cycle
            status = f"error ({exc})"
            log.warning("fetch failed for %s: %s", label, exc)
        await session.execute(
            update(NewsFeed)
            .where(NewsFeed.id == feed.id)
            .values(last_fetch=datetime.now(timezone.utc), last_status=status)
        )
        await session.commit()
        results[label] = status
        log.info("%s: %s", label, status)
    return results
