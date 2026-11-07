"""DB-backed tests for the news feature (registry sync, article upsert, API).

Runs on the suite's temporary database (see conftest.py), emptied before each
test, so every assertion is against this module's own seed data.
"""

from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select, text

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


def _use_sources(monkeypatch, test_sources):
    monkeypatch.setattr(registry, "SOURCES", test_sources)


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
    _use_sources(monkeypatch, TEST_SOURCES_V1)
    await registry.sync_registry(news_db_session)

    feeds = await _feeds(news_db_session, "test-outlet")
    assert [(f.category, f.position) for f in feeds] == [("sports", 0), ("news", 1)]

    # Re-sync with the sports feed removed and the source renamed.
    _use_sources(monkeypatch, TEST_SOURCES_V2)
    await registry.sync_registry(news_db_session)

    feeds = await _feeds(news_db_session, "test-outlet")
    assert [f.category for f in feeds] == ["news"]
    name = (
        await news_db_session.execute(
            select(NewsSource.name).where(NewsSource.slug == "test-outlet")
        )
    ).scalar_one()
    assert name == "Test Outlet Renamed"


TEST_SOURCE_GONE = {
    "slug": "test-gone",
    "name": "Test Gone",
    "homepage": "https://gone.example.com",
    "enabled": True,
    "feeds": [{"category": "news", "url": "https://gone.example.com/feed"}],
}


async def _slugs(session):
    return set((await session.execute(select(NewsSource.slug))).scalars().all())


async def test_registry_sync_deletes_sources_removed_from_registry(news_db_session, monkeypatch):
    _use_sources(monkeypatch, TEST_SOURCES_V1 + [TEST_SOURCE_GONE])
    await registry.sync_registry(news_db_session)
    gone_id = (
        await news_db_session.execute(select(NewsSource.id).where(NewsSource.slug == "test-gone"))
    ).scalar_one()
    await upsert_articles(news_db_session, [_article(gone_id, "gone-1", "news")])
    await news_db_session.commit()

    # Re-sync with test-gone dropped entirely from the registry.
    _use_sources(monkeypatch, TEST_SOURCES_V1)
    await registry.sync_registry(news_db_session)

    assert await _slugs(news_db_session) == {"test-outlet"}
    assert await _feeds(news_db_session, "test-gone") == []
    orphans = (
        await news_db_session.execute(
            select(NewsArticle.id).where(NewsArticle.source_id == gone_id)
        )
    ).all()
    assert orphans == []  # articles cascaded


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
    _use_sources(monkeypatch, TEST_SOURCES_V1)
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
    # Assign the cluster directly — clustering has its own offline tests.
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
    (story,) = payload["stories"]
    assert story["id"] == arts[0].id
    assert story["title"] == "Test story headline"
    assert story["category"] == "sports"
    assert story["article_count"] == 2 and story["source_count"] == 1

    sources = (await api_get_sources(session=news_db_session))["sources"]
    # Per-source total: every feed row of the outlet reports its 2 stored
    # articles, even the "news" feed whose section none of them were filed under.
    assert [(r["slug"], r["category"], r["article_count"]) for r in sources] == [
        ("test-outlet", "sports", 2),
        ("test-outlet", "news", 2),
    ]
    assert sources[0]["last_status"] is None  # never fetched in this test


async def _seed_singleton_stories(session, monkeypatch, count: int) -> list[int]:
    """Seed `count` articles, each its own single-article cluster, published at
    staggered times so their stories sort deterministically newest-first.

    Returns the cluster ids in newest-activity-first order.
    """
    sid = await _seed_source(session, monkeypatch)
    now = datetime.now(timezone.utc)
    arts = [_article(sid, f"lim-{i}", "news", title=f"test-limit story {i}") for i in range(count)]
    # Stagger published times: lim-0 newest, lim-{count-1} oldest.
    for i, a in enumerate(arts):
        a["published"] = now - timedelta(minutes=i)
    await upsert_articles(session, arts)
    await session.commit()
    rows = (
        (
            await session.execute(
                select(NewsArticle)
                .where(NewsArticle.source_id == sid)
                .order_by(NewsArticle.published.desc())
            )
        )
        .scalars()
        .all()
    )
    for a in rows:  # each article is its own cluster
        a.cluster_id = a.id
    await session.commit()
    return [a.id for a in rows]


async def test_stories_limit_returns_newest_slice(news_db_session, monkeypatch):
    ids_newest_first = await _seed_singleton_stories(news_db_session, monkeypatch, count=8)

    payload = await api_get_stories(hours=24, limit=5, session=news_db_session)
    # Exactly the 5 newest, still sorted latest-activity first, with the label map.
    assert [s["id"] for s in payload["stories"]] == ids_newest_first[:5]
    assert payload["categories"]["news"] == "News"


async def test_stories_omitted_limit_returns_full_window(news_db_session, monkeypatch):
    ids_newest_first = await _seed_singleton_stories(news_db_session, monkeypatch, count=8)

    payload = await api_get_stories(hours=24, session=news_db_session)
    ids = [s["id"] for s in payload["stories"]]
    assert ids == ids_newest_first  # all 8, newest-first, nothing dropped


# --- future-dated articles: published is capped at fetched_at ---------------


async def _stored_times(session, sid, guid):
    return (
        await session.execute(
            select(NewsArticle.published, NewsArticle.fetched_at).where(
                NewsArticle.source_id == sid, NewsArticle.guid == guid
            )
        )
    ).one()


async def test_future_dated_article_is_capped_at_fetch_time(news_db_session, monkeypatch):
    sid = await _seed_source(news_db_session, monkeypatch)
    art = _article(sid, "future", "news")
    art["published"] = art["fetched_at"] + timedelta(days=30)
    await upsert_articles(news_db_session, [art])
    await news_db_session.commit()

    published, fetched_at = await _stored_times(news_db_session, sid, "future")
    assert published == fetched_at == art["fetched_at"]


async def test_past_dated_article_keeps_feed_date(news_db_session, monkeypatch):
    sid = await _seed_source(news_db_session, monkeypatch)
    art = _article(sid, "past", "news")
    art["published"] = art["fetched_at"] - timedelta(hours=3)
    await upsert_articles(news_db_session, [art])
    await news_db_session.commit()

    published, _ = await _stored_times(news_db_session, sid, "past")
    assert published == art["published"]


async def test_refetch_does_not_move_capped_article(news_db_session, monkeypatch):
    sid = await _seed_source(news_db_session, monkeypatch)
    first = _article(sid, "pinned", "news")
    claimed = first["fetched_at"] + timedelta(days=30)
    first["published"] = claimed
    await upsert_articles(news_db_session, [first])
    await news_db_session.commit()

    # Re-fetched after the claimed date has passed: the feed still carries the
    # original date, and this fetch's fetched_at is later than it.
    again = _article(sid, "pinned", "news")
    again["published"] = claimed
    again["fetched_at"] = claimed + timedelta(days=1)
    await upsert_articles(news_db_session, [again])
    await news_db_session.commit()

    published, fetched_at = await _stored_times(news_db_session, sid, "pinned")
    assert published == fetched_at == first["fetched_at"]


def _backfill_sql() -> str:
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "0009_clamp_future_article_dates.py"
    )
    spec = importlib.util.spec_from_file_location("migration_0009", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.BACKFILL_SQL


async def test_backfill_corrects_only_future_dated_rows(news_db_session, monkeypatch):
    sid = await _seed_source(news_db_session, monkeypatch)
    await upsert_articles(
        news_db_session, [_article(sid, g, "news") for g in ("ahead", "behind", "equal")]
    )
    await news_db_session.commit()
    # Write pre-cap data directly, bypassing upsert_articles' cap.
    fetched = datetime(2026, 10, 28, 16, 31, tzinfo=timezone.utc)
    seeded = {
        "ahead": fetched + timedelta(days=30),
        "behind": fetched - timedelta(hours=2),
        "equal": fetched,
    }
    for guid, published in seeded.items():
        await news_db_session.execute(
            text(
                "UPDATE news_articles SET published = :p, fetched_at = :f "
                "WHERE source_id = :s AND guid = :g"
            ),
            {"p": published, "f": fetched, "s": sid, "g": guid},
        )
    await news_db_session.commit()

    await news_db_session.execute(text(_backfill_sql()))
    await news_db_session.commit()

    stored = {g: (await _stored_times(news_db_session, sid, g)) for g in seeded}
    assert stored["ahead"] == (fetched, fetched)
    assert stored["behind"] == (seeded["behind"], fetched)
    assert stored["equal"] == (fetched, fetched)


async def test_capped_article_sorts_by_fetch_time(news_db_session, monkeypatch):
    sid = await _seed_source(news_db_session, monkeypatch)
    now = datetime.now(timezone.utc)
    pinned = _article(sid, "pinned", "news", title="test-cap pinned schedule")
    pinned["fetched_at"] = now - timedelta(hours=2)
    pinned["published"] = now + timedelta(days=30)
    fresh = _article(sid, "fresh", "news", title="test-cap fresh story")
    fresh["published"] = now - timedelta(minutes=10)
    await upsert_articles(news_db_session, [pinned, fresh])
    await news_db_session.commit()
    rows = (
        (await news_db_session.execute(select(NewsArticle).where(NewsArticle.source_id == sid)))
        .scalars()
        .all()
    )
    for a in rows:  # each article is its own cluster
        a.cluster_id = a.id
    await news_db_session.commit()

    payload = await api_get_stories(hours=24, session=news_db_session)
    assert [s["title"] for s in payload["stories"]] == [
        "test-cap fresh story",
        "test-cap pinned schedule",
    ]
