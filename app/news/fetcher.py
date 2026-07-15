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

import feedparser
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.news.classify import classify
from app.news.models import NewsArticle, NewsFeed, NewsSource
from app.news.registry import USER_AGENT
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


async def fetch_feed(session: AsyncSession, feed: NewsFeed) -> tuple[int, str]:
    """Fetch one feed. Returns (changed article count, status)."""
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
                # last-resort fallback inside classify()).
                "category": classify(title, summary, _entry_tags(entry), feed.category),
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
            _, status = await fetch_feed(session, feed)
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
