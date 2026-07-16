"""Read model: turn clustered articles into story objects for the API.

Ported from ChattNews. build_stories() is pure (testable offline);
get_stories()/get_sources() are the async DB entry points used by the router.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.news.models import NewsArticle, NewsFeed, NewsSource
from app.news.textutil import truncate_sentences


def build_stories(rows: list[dict]) -> list[dict]:
    """Group article rows (sorted by published ASC) into story dicts.

    Each row: id, cluster_id, url, title, summary, category, published (ISO
    string), source_name, source_slug.
    """
    clusters: dict[int, list[dict]] = {}
    for row in rows:
        clusters.setdefault(row["cluster_id"], []).append(row)

    stories = []
    for cluster_id, members in clusters.items():
        # Headline from the first report; summary from the wordiest one.
        best_summary = max((m["summary"] for m in members), key=len)
        # Majority category; a specific section beats generic 'news' on ties.
        votes = Counter(m["category"] for m in members)
        category = max(votes.items(), key=lambda kv: (kv[1], kv[0] != "news"))[0]
        # Lead image borrowed from the earliest member that has one (members are
        # published-ascending), consistent with the headline coming from members[0].
        image_url = next((m["image_url"] for m in members if m.get("image_url")), None)
        seen_sources = set()
        source_links = []
        for m in members:
            # One link per source per story keeps update-spam collapsed.
            if m["source_slug"] in seen_sources:
                continue
            seen_sources.add(m["source_slug"])
            source_links.append(
                {
                    "source": m["source_name"],
                    "slug": m["source_slug"],
                    "title": m["title"],
                    "url": m["url"],
                    "published": m["published"],
                }
            )
        stories.append(
            {
                "id": cluster_id,
                "title": members[0]["title"],
                "summary": truncate_sentences(best_summary, 400),
                "category": category,
                "image_url": image_url,
                "first_published": members[0]["published"],
                "latest_published": members[-1]["published"],
                "source_count": len(seen_sources),
                "article_count": len(members),
                "sources": source_links,
            }
        )

    stories.sort(key=lambda s: s["latest_published"], reverse=True)
    return stories


async def get_stories(
    session: AsyncSession, hours: int = 72, limit: int | None = None
) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = (
        await session.execute(
            select(
                NewsArticle.id,
                NewsArticle.cluster_id,
                NewsArticle.url,
                NewsArticle.title,
                NewsArticle.summary,
                NewsArticle.category,
                NewsArticle.published,
                NewsArticle.image_url,
                NewsSource.name.label("source_name"),
                NewsSource.slug.label("source_slug"),
            )
            .join(NewsSource, NewsSource.id == NewsArticle.source_id)
            .where(NewsArticle.published >= cutoff, NewsArticle.cluster_id.isnot(None))
            .order_by(NewsArticle.published.asc())
        )
    ).all()
    stories = build_stories(
        [
            {
                "id": r.id,
                "cluster_id": r.cluster_id,
                "url": r.url,
                "title": r.title,
                "summary": r.summary,
                "category": r.category,
                "published": r.published.isoformat(),
                "image_url": r.image_url,
                "source_name": r.source_name,
                "source_slug": r.source_slug,
            }
            for r in rows
        ]
    )
    # Stories are clusters built in Python, so the limit is a post-sort slice of
    # the newest-activity-first list, not a SQL LIMIT on the article rows.
    return stories[:limit] if limit is not None else stories


async def get_sources(session: AsyncSession) -> list[dict]:
    """One row per feed, with the source's total article count.

    Category is content-derived and no longer equals the producing feed's
    section, so the count is a per-source total rather than per source+category.
    """
    article_count = (
        select(func.count())
        .select_from(NewsArticle)
        .where(NewsArticle.source_id == NewsSource.id)
        .correlate(NewsSource)
        .scalar_subquery()
    )
    rows = (
        await session.execute(
            select(
                NewsSource.slug,
                NewsSource.name,
                NewsSource.homepage,
                NewsSource.enabled,
                NewsFeed.category,
                NewsFeed.last_fetch,
                NewsFeed.last_status,
                article_count.label("article_count"),
            )
            .join(NewsSource, NewsSource.id == NewsFeed.source_id)
            .order_by(NewsSource.name, NewsFeed.position)
        )
    ).all()
    return [
        {
            "slug": r.slug,
            "name": r.name,
            "homepage": r.homepage,
            "enabled": r.enabled,
            "category": r.category,
            "last_fetch": r.last_fetch.isoformat() if r.last_fetch else None,
            "last_status": r.last_status,
            "article_count": r.article_count,
        }
        for r in rows
    ]
