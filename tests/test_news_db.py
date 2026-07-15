"""DB-backed tests for the news feature (registry sync, article upsert, API).

Same auto-skip pattern as the timeseries DB tests: the news_db_session fixture
skips when Postgres is unreachable or migration 0002 hasn't been applied. All
rows use 'test-' slugs so real registry data is untouched.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

import app.news.registry as registry
from app.api.news import get_sources as api_get_sources
from app.api.news import get_stories as api_get_stories
from app.news.fetcher import upsert_articles
from app.news.models import NewsArticle, NewsFeed, NewsSource

TEST_SOURCES_V1 = [
    {
        "slug": "test-outlet",
        "name": "Test Outlet",
        "homepage": "https://test.example.com",
        "enabled": True,
        "feeds": [
            {"category": "sports", "url": "https://test.example.com/sports/feed"},
            {"category": "news", "url": "https://test.example.com/news/feed"},
        ],
    },
]

# v2: renamed, sports feed removed.
TEST_SOURCES_V2 = [
    {
        "slug": "test-outlet",
        "name": "Test Outlet Renamed",
        "homepage": "https://test.example.com",
        "enabled": True,
        "feeds": [
            {"category": "news", "url": "https://test.example.com/news/feed"},
        ],
    },
]


async def _feeds(session, slug):
    return (
        (
            await session.execute(
                select(NewsFeed)
                .join(NewsSource, NewsSource.id == NewsFeed.source_id)
                .where(NewsSource.slug == slug)
                .order_by(NewsFeed.position)
            )
        )
        .scalars()
        .all()
    )


async def test_registry_sync_upserts_and_deletes(news_db_session, monkeypatch):
    monkeypatch.setattr(registry, "SOURCES", TEST_SOURCES_V1)
    await registry.sync_registry(news_db_session)

    feeds = await _feeds(news_db_session, "test-outlet")
    assert [(f.category, f.position) for f in feeds] == [("sports", 0), ("news", 1)]

    # Re-sync with the sports feed removed and the source renamed.
    monkeypatch.setattr(registry, "SOURCES", TEST_SOURCES_V2)
    await registry.sync_registry(news_db_session)

    feeds = await _feeds(news_db_session, "test-outlet")
    assert [f.category for f in feeds] == ["news"]
    name = (
        await news_db_session.execute(
            select(NewsSource.name).where(NewsSource.slug == "test-outlet")
        )
    ).scalar_one()
    assert name == "Test Outlet Renamed"


def _article(source_id, guid, category, title="Some headline"):
    now = datetime.now(timezone.utc)
    return {
        "source_id": source_id,
        "guid": guid,
        "url": f"https://test.example.com/{guid}",
        "title": title,
        "summary": "",
        "category": category,
        "published": now,
        "fetched_at": now,
    }


async def _seed_source(session, monkeypatch) -> int:
    monkeypatch.setattr(registry, "SOURCES", TEST_SOURCES_V1)
    await registry.sync_registry(session)
    return (
        await session.execute(select(NewsSource.id).where(NewsSource.slug == "test-outlet"))
    ).scalar_one()


async def test_article_dedup_and_category_recompute(news_db_session, monkeypatch):
    sid = await _seed_source(news_db_session, monkeypatch)

    assert await upsert_articles(news_db_session, [_article(sid, "g1", "news")]) == 1
    # Same guid, freshly classified category: overwrites in place, no new row.
    assert await upsert_articles(news_db_session, [_article(sid, "g1", "sports")]) == 1
    # Recompute is not a one-way upgrade — a later fetch can move it back.
    assert await upsert_articles(news_db_session, [_article(sid, "g1", "news")]) == 1
    # Duplicate guids within one payload: first occurrence wins, one row.
    assert (
        await upsert_articles(
            news_db_session, [_article(sid, "g2", "news"), _article(sid, "g2", "sports")]
        )
        == 1
    )
    await news_db_session.commit()

    rows = (
        await news_db_session.execute(
            select(NewsArticle.guid, NewsArticle.category)
            .where(NewsArticle.source_id == sid)
            .order_by(NewsArticle.guid)
        )
    ).all()
    assert [tuple(r) for r in rows] == [("g1", "news"), ("g2", "news")]


async def test_stories_and_sources_api_round_trip(news_db_session, monkeypatch):
    sid = await _seed_source(news_db_session, monkeypatch)
    await upsert_articles(
        news_db_session,
        [
            _article(sid, "g1", "sports", title="Test story headline"),
            _article(sid, "g2", "sports", title="Test story headline follow-up"),
        ],
    )
    await news_db_session.commit()
    # Assign the cluster directly — clustering has its own offline tests, and
    # calling recluster() here would rewrite real rows in a shared dev DB.
    arts = (
        (
            await news_db_session.execute(
                select(NewsArticle).where(NewsArticle.source_id == sid).order_by(NewsArticle.id)
            )
        )
        .scalars()
        .all()
    )
    for a in arts:
        a.cluster_id = arts[0].id
    await news_db_session.commit()

    payload = await api_get_stories(hours=1, session=news_db_session)
    assert payload["categories"]["sports"] == "Sports"
    story = next(s for s in payload["stories"] if s["id"] == arts[0].id)
    assert story["title"] == "Test story headline"
    assert story["category"] == "sports"
    assert story["article_count"] == 2 and story["source_count"] == 1

    sources = (await api_get_sources(session=news_db_session))["sources"]
    # Per-source total: every feed row of the outlet reports its 2 stored
    # articles, even the "news" feed whose section none of them were filed under.
    for cat in ("sports", "news"):
        row = next(r for r in sources if r["slug"] == "test-outlet" and r["category"] == cat)
        assert row["article_count"] == 2
    sports_row = next(
        r for r in sources if r["slug"] == "test-outlet" and r["category"] == "sports"
    )
    assert sports_row["last_status"] is None  # never fetched in this test
