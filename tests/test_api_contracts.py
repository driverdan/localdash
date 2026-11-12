"""Golden-response tests: the exact JSON every /api/v1 route serves.

Each test seeds known rows (or fixture payloads), calls the route through the
ASGI app, and compares the body to a literal expected value twice: as parsed
JSON (readable diffs) and as the exact bytes FastAPI's JSONResponse renders
from that value, so key order, `null` fields, integer vs float rendering and
`+00:00` (never `Z`) timestamps are all pinned. These were written before the
response models existed and must not change when a route gains one.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from functools import partial

import feedparser
import httpx
import pytest
from sqlalchemy import select

import app.api.weather as weather_api
import app.collect as collect_mod
import app.events.refresh as events_refresh_mod
import app.news.fetcher as news_fetcher_mod
import app.news.refresh as news_refresh_mod
import app.news.stories as stories_mod
from app.collectors.base import NormalizedObservation
from app.config import get_settings
from app.events.dedup import canonical_key
from app.events.models import Event, EventLink, Tag
from app.events.sources.base import RawEvent
from app.geo import ewkt_point
from app.ingest import ingest
from app.main import app
from app.models import Source
from app.news.models import NewsArticle, NewsFeed, NewsSource
from app.weather.service import AIRNOW_URL
from tests.conftest import make_settings
from tests.test_live_signals import FakeManager, FakeNominatimGeocoder
from tests.test_weather import OBS_KCHA, FakeNWS, _load, _load_airnow

T1 = datetime(2026, 7, 10, 10, 0, tzinfo=UTC)
T2 = datetime(2026, 7, 10, 10, 5, 30, 250000, tzinfo=UTC)  # non-zero microseconds
NEWS_NOW = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)
FUTURE = datetime(2099, 6, 1, 18, 0, tzinfo=UTC)
CENTER = (35.0456, -85.3097)  # make_settings() default center


def _wire(expected) -> bytes:
    """The bytes Starlette's JSONResponse renders for `expected`."""
    return json.dumps(
        expected, ensure_ascii=False, allow_nan=False, indent=None, separators=(",", ":")
    ).encode("utf-8")


def _check(response: httpx.Response, expected) -> None:
    assert response.status_code == 200, response.text
    assert response.json() == expected
    assert response.content == _wire(expected)


@pytest.fixture
async def client(db_session):
    """ASGI client on the app, against the run's emptied temporary database."""
    app.state.collectors = {}
    app.dependency_overrides[get_settings] = lambda: make_settings()
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_settings, None)


# --- app shell ------------------------------------------------------------------


async def test_config(client):
    s = make_settings()
    r = await client.get("/api/v1/config")
    _check(r, {"tile_url": s.tile_url, "tile_attribution": s.tile_attribution})


# --- timeseries -----------------------------------------------------------------


RING = [[-85.3, 35.0], [-85.3, 35.1], [-85.2, 35.1], [-85.2, 35.0], [-85.3, 35.0]]


async def _seed_timeseries(session) -> None:
    """Entity 1 (`a`): a point, then a polygon. Entity 2 (`b`): closed at T2."""
    a_props = {"agency": "CPD", "priority": 2, "status": "upstream-status", "id": "upstream-id"}
    await ingest(
        session,
        "test-golden",
        [
            NormalizedObservation(
                external_id="a",
                category="police",
                label="Traffic stop",
                lat=35.05,
                lon=-85.31,
                status="Queued",
                properties=a_props,
            ),
            NormalizedObservation(
                external_id="b",
                category="fire",
                label="Alarm",
                lat=35.1,
                lon=-85.2,
                status="Enroute",
                properties={"units": ["E1", "L2"]},
            ),
        ],
        now=T1,
    )
    await ingest(
        session,
        "test-golden",
        [
            NormalizedObservation(
                external_id="a",
                category="police",
                label="Traffic stop",
                geometry={"type": "Polygon", "coordinates": [RING]},
                status="Queued",
                properties=a_props,
            ),
        ],
        now=T2,
    )


async def test_timeseries_entities_active(client, db_session):
    await _seed_timeseries(db_session)
    r = await client.get("/api/v1/timeseries/entities", params={"source": "test-golden"})
    _check(r, EXPECTED_ENTITIES_ACTIVE)


async def test_timeseries_entities_inactive(client, db_session):
    await _seed_timeseries(db_session)
    r = await client.get(
        "/api/v1/timeseries/entities", params={"source": "test-golden", "active": "false"}
    )
    _check(r, EXPECTED_ENTITIES_INACTIVE)


async def test_timeseries_entity_detail(client, db_session):
    await _seed_timeseries(db_session)
    r = await client.get("/api/v1/timeseries/entities/1")
    _check(r, EXPECTED_ENTITY_DETAIL)


async def test_timeseries_entity_track(client, db_session):
    await _seed_timeseries(db_session)
    r = await client.get("/api/v1/timeseries/entities/1/track")
    _check(r, EXPECTED_TRACK)


async def test_timeseries_observations(client, db_session):
    await _seed_timeseries(db_session)
    r = await client.get("/api/v1/timeseries/observations", params={"source": "test-golden"})
    _check(r, EXPECTED_OBSERVATIONS)


async def test_timeseries_sources(client, db_session):
    db_session.add_all(
        [
            Source(
                key="test-ran",
                name="Ran Source",
                enabled=True,
                poll_interval_seconds=60,
                last_run_at=T2,
                last_status="ok",
                last_error=None,
                last_count=12,
            ),
            Source(
                key="test-failed",
                name="Failed Source",
                enabled=True,
                poll_interval_seconds=300,
                last_run_at=T1,
                last_status="error",
                last_error="boom",
                last_count=0,
            ),
            Source(key="test-never", name="Never Ran", enabled=False, poll_interval_seconds=30),
        ]
    )
    await db_session.commit()
    r = await client.get("/api/v1/timeseries/sources")
    _check(r, EXPECTED_SOURCES)


# --- news -----------------------------------------------------------------------


async def _seed_news(session) -> None:
    """Two outlets. Story 1: three articles from both outlets; story 4: one article."""
    one = NewsSource(slug="test-one", name="Outlet One", homepage="https://one.test", enabled=True)
    two = NewsSource(slug="test-two", name="Outlet Two", homepage="https://two.test", enabled=True)
    session.add_all([one, two])
    await session.flush()
    session.add_all(
        [
            NewsFeed(
                source_id=one.id,
                url="https://one.test/sports/feed",
                category="sports",
                position=0,
                last_fetch=T2,
                last_status="ok (3 entries, 1 changed)",
            ),
            NewsFeed(source_id=one.id, url="https://one.test/feed", category="news", position=1),
            NewsFeed(
                source_id=two.id,
                url="https://two.test/feed",
                category="news",
                position=0,
                last_fetch=T1,
                last_status="error (HTTP 404)",
            ),
        ]
    )

    def art(source_id, guid, title, summary, category, published, image_url=None):
        return NewsArticle(
            source_id=source_id,
            guid=guid,
            url=f"https://news.test/{guid}",
            title=title,
            summary=summary,
            category=category,
            published=published,
            fetched_at=published,
            image_url=image_url,
        )

    session.add_all(
        [
            art(one.id, "g1", "Bridge closes for repairs", "Short.", "news", T1),
            art(
                two.id,
                "g2",
                "Bridge closure begins",
                "A longer summary. It has two sentences.",
                "news",
                T1 + timedelta(minutes=30),
                image_url="https://img.test/bridge.jpg",
            ),
            art(
                one.id,
                "g3",
                "Bridge update",
                "Update.",
                "sports",
                T1 + timedelta(minutes=45, microseconds=250000),
            ),
            art(two.id, "g4", "Mocs win opener", "", "sports", T1 + timedelta(hours=1)),
        ]
    )
    await session.flush()
    articles = {a.guid: a for a in (await session.execute(select(NewsArticle))).scalars()}
    for guid in ("g1", "g2", "g3"):
        articles[guid].cluster_id = articles["g1"].id
    articles["g4"].cluster_id = articles["g4"].id
    await session.commit()


async def test_news_stories(client, db_session, monkeypatch):
    await _seed_news(db_session)
    monkeypatch.setattr(stories_mod, "get_stories", partial(stories_mod.get_stories, now=NEWS_NOW))
    r = await client.get("/api/v1/news/stories")
    _check(r, EXPECTED_STORIES)


async def test_news_sources(client, db_session):
    await _seed_news(db_session)
    r = await client.get("/api/v1/news/sources")
    _check(r, EXPECTED_NEWS_SOURCES)


# --- events ---------------------------------------------------------------------


async def _seed_events(session) -> None:
    music = Tag(name="music")
    food = Tag(name="food")
    session.add_all(
        [
            Event(
                canonical_key=canonical_key("test-Jazz Night", FUTURE),
                title="test-Jazz Night",
                description="Live jazz.",
                starts_at=FUTURE,
                ends_at=FUTURE + timedelta(hours=3),
                venue_name="The Club",
                address="1 Main St, Chattanooga, TN",
                image_url="https://img.test/jazz.jpg",
                location=ewkt_point(*CENTER),
                tags=[music, food],
                links=[
                    EventLink(source_name="test-a", source_url="https://a.test/jazz"),
                    EventLink(source_name="test-b", source_url="https://b.test/jazz"),
                ],
            ),
            Event(
                canonical_key=canonical_key("test-Far Fair", FUTURE + timedelta(days=1)),
                title="test-Far Fair",
                description="",
                starts_at=FUTURE + timedelta(days=1),
                location=ewkt_point(35.2, -85.1),
                tags=[food],
                links=[EventLink(source_name="test-a", source_url="https://a.test/fair")],
            ),
            Event(
                canonical_key=canonical_key("test-Unlocated Talk", FUTURE + timedelta(days=2)),
                title="test-Unlocated Talk",
                description="",
                starts_at=FUTURE + timedelta(days=2, microseconds=5),
                links=[],
            ),
        ]
    )
    await session.commit()


async def test_events_items(client, db_session):
    await _seed_events(db_session)
    r = await client.get("/api/v1/events/items")
    _check(r, EXPECTED_EVENTS)


async def test_events_tags(client, db_session):
    await _seed_events(db_session)
    r = await client.get("/api/v1/events/tags")
    _check(r, {"tags": ["food", "music"]})


# --- weather --------------------------------------------------------------------


async def test_weather_current(client, mock_http, monkeypatch):
    nws = FakeNWS(mock_http, airnow_api_key="test-key")
    observation = _load("observation")
    observation["properties"]["windSpeed"]["value"] = None
    nws.routes[OBS_KCHA] = observation
    nws.routes[AIRNOW_URL] = _load_airnow("current")
    monkeypatch.setattr(weather_api, "service", nws.service())
    r = await client.get("/api/v1/weather/current")
    _check(r, EXPECTED_WEATHER)


# --- refresh routes -------------------------------------------------------------


class _GoldenEventSource:
    name = "test-golden"

    async def fetch(self) -> list[RawEvent]:
        def raw(source_name):
            return RawEvent(
                title="test-Refresh Show",
                start_time=FUTURE,
                source_name=source_name,
                source_url=f"https://{source_name}.test/show",
                latitude=CENTER[0],
                longitude=CENTER[1],
            )

        return [raw("test-a"), raw("test-b")]


async def test_events_refresh(client, db_session, monkeypatch):
    settings = make_settings(
        events_ical_feeds="", events_geocode_retry_hours=0, events_ingest_max_miles=0
    )
    monkeypatch.setattr(events_refresh_mod, "get_settings", lambda: settings)
    monkeypatch.setattr(events_refresh_mod, "build_sources", lambda s: [_GoldenEventSource()])
    monkeypatch.setattr(events_refresh_mod, "NominatimGeocoder", FakeNominatimGeocoder)
    monkeypatch.setattr(events_refresh_mod, "manager", FakeManager())
    r = await client.post("/api/v1/events/refresh")
    _check(
        r,
        {"created": 1, "merged": 1, "skipped_far": 0, "retried": 0, "resolved": 0, "reconciled": 0},
    )


RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Golden</title><link>https://one.test</link>
<item><title>Golden refresh story</title><link>https://one.test/golden</link>
<guid>golden-1</guid><pubDate>{pub}</pubDate><description>Body.</description></item>
</channel></rss>"""


async def test_news_refresh(client, db_session, monkeypatch):
    src = NewsSource(slug="test-one", name="Outlet One", homepage="https://one.test", enabled=True)
    db_session.add(src)
    await db_session.flush()
    db_session.add(NewsFeed(source_id=src.id, url="https://one.test/feed", category="news"))
    await db_session.commit()
    pub = (datetime.now(UTC) - timedelta(hours=1)).strftime("%a, %d %b %Y %H:%M:%S +0000")
    # feedparser fetches RSS itself (urllib, not app.http), so feed it the document.
    monkeypatch.setattr(
        news_fetcher_mod, "_parse_feed", lambda url: feedparser.parse(RSS.format(pub=pub))
    )
    monkeypatch.setattr(news_refresh_mod, "manager", FakeManager())
    r = await client.post("/api/v1/news/refresh")
    _check(r, {"sources": {"test-one/news": "ok (1 entries, 1 changed)"}, "clusters": 1})


class _GoldenCollector:
    source_key = "test-golden"
    name = "Golden"
    poll_interval = 60

    async def collect(self):
        return [
            NormalizedObservation(external_id="x", lat=35.0, lon=-85.0, status="Open"),
            NormalizedObservation(external_id="y", lat=35.1, lon=-85.1, status="Open"),
        ]


class _FailingCollector(_GoldenCollector):
    source_key = "test-failing"

    async def collect(self):
        raise RuntimeError("upstream down")


async def test_timeseries_source_refresh(client, monkeypatch):
    monkeypatch.setattr(collect_mod, "manager", FakeManager())
    app.state.collectors = {"test-golden": _GoldenCollector(), "test-failing": _FailingCollector()}
    r = await client.post("/api/v1/timeseries/sources/test-golden/refresh")
    _check(r, {"source": "test-golden", "status": "ok", "error": None, "count": 2})
    r = await client.post("/api/v1/timeseries/sources/test-failing/refresh")
    _check(r, {"source": "test-failing", "status": "error", "error": "upstream down", "count": 0})


# --- expected bodies ------------------------------------------------------------

EXPECTED_ENTITIES_ACTIVE = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[-85.3, 35], [-85.3, 35.1], [-85.2, 35.1], [-85.2, 35], [-85.3, 35]]
                ],
            },
            "properties": {
                "id": 1,
                "agency": "CPD",
                "status": "Queued",
                "priority": 2,
                "source": "test-golden",
                "external_id": "a",
                "category": "police",
                "label": "Traffic stop",
                "last_seen_at": "2026-07-10T10:05:30.250000+00:00",
                "active": True,
            },
            "id": 1,
        }
    ],
}
EXPECTED_ENTITIES_INACTIVE = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-85.2, 35.1]},
            "properties": {
                "units": ["E1", "L2"],
                "status": "Closed",
                "id": 2,
                "source": "test-golden",
                "external_id": "b",
                "category": "fire",
                "label": "Alarm",
                "last_seen_at": "2026-07-10T10:05:30.250000+00:00",
                "active": False,
            },
            "id": 2,
        }
    ],
}
EXPECTED_ENTITY_DETAIL = {
    "id": 1,
    "source": "test-golden",
    "external_id": "a",
    "category": "police",
    "label": "Traffic stop",
    "is_active": True,
    "first_seen_at": "2026-07-10T10:00:00+00:00",
    "last_seen_at": "2026-07-10T10:05:30.250000+00:00",
    "latest_properties": {"id": "upstream-id", "agency": "CPD", "status": "Queued", "priority": 2},
}
EXPECTED_TRACK = [
    {
        "observed_at": "2026-07-10T10:00:00+00:00",
        "status": "Queued",
        "geometry": {"type": "Point", "coordinates": [-85.31, 35.05]},
        "lon": -85.31,
        "lat": 35.05,
        "properties": {
            "id": "upstream-id",
            "agency": "CPD",
            "status": "upstream-status",
            "priority": 2,
        },
    },
    {
        "observed_at": "2026-07-10T10:05:30.250000+00:00",
        "status": "Queued",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[-85.3, 35], [-85.3, 35.1], [-85.2, 35.1], [-85.2, 35], [-85.3, 35]]],
        },
        "lon": None,
        "lat": None,
        "properties": {
            "id": "upstream-id",
            "agency": "CPD",
            "status": "upstream-status",
            "priority": 2,
        },
    },
]
EXPECTED_OBSERVATIONS = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[-85.3, 35], [-85.3, 35.1], [-85.2, 35.1], [-85.2, 35], [-85.3, 35]]
                ],
            },
            "properties": {
                "entity_id": 1,
                "source": "test-golden",
                "category": "police",
                "status": "upstream-status",
                "observed_at": "2026-07-10T10:05:30.250000+00:00",
                "id": "upstream-id",
                "agency": "CPD",
                "priority": 2,
            },
        },
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-85.2, 35.1]},
            "properties": {
                "entity_id": 2,
                "source": "test-golden",
                "category": "fire",
                "status": "Closed",
                "observed_at": "2026-07-10T10:05:30.250000+00:00",
                "reason": "absent_from_feed",
            },
        },
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-85.31, 35.05]},
            "properties": {
                "entity_id": 1,
                "source": "test-golden",
                "category": "police",
                "status": "upstream-status",
                "observed_at": "2026-07-10T10:00:00+00:00",
                "id": "upstream-id",
                "agency": "CPD",
                "priority": 2,
            },
        },
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-85.2, 35.1]},
            "properties": {
                "entity_id": 2,
                "source": "test-golden",
                "category": "fire",
                "status": "Enroute",
                "observed_at": "2026-07-10T10:00:00+00:00",
                "units": ["E1", "L2"],
            },
        },
    ],
}
EXPECTED_SOURCES = [
    {
        "key": "test-ran",
        "name": "Ran Source",
        "enabled": True,
        "poll_interval_seconds": 60,
        "last_run_at": "2026-07-10T10:05:30.250000+00:00",
        "last_status": "ok",
        "last_error": None,
        "last_count": 12,
    },
    {
        "key": "test-failed",
        "name": "Failed Source",
        "enabled": True,
        "poll_interval_seconds": 300,
        "last_run_at": "2026-07-10T10:00:00+00:00",
        "last_status": "error",
        "last_error": "boom",
        "last_count": 0,
    },
    {
        "key": "test-never",
        "name": "Never Ran",
        "enabled": False,
        "poll_interval_seconds": 30,
        "last_run_at": None,
        "last_status": None,
        "last_error": None,
        "last_count": None,
    },
]
EXPECTED_STORIES = {
    "categories": {
        "news": "News",
        "sports": "Sports",
        "business": "Business",
        "politics": "Politics",
        "opinion": "Opinion",
        "life": "Life",
    },
    "stories": [
        {
            "id": 4,
            "title": "Mocs win opener",
            "summary": "",
            "category": "sports",
            "image_url": None,
            "first_published": "2026-07-10T11:00:00+00:00",
            "latest_published": "2026-07-10T11:00:00+00:00",
            "source_count": 1,
            "article_count": 1,
            "sources": [
                {
                    "source": "Outlet Two",
                    "slug": "test-two",
                    "title": "Mocs win opener",
                    "url": "https://news.test/g4",
                    "published": "2026-07-10T11:00:00+00:00",
                }
            ],
        },
        {
            "id": 1,
            "title": "Bridge closes for repairs",
            "summary": "A longer summary. It has two sentences.",
            "category": "news",
            "image_url": "https://img.test/bridge.jpg",
            "first_published": "2026-07-10T10:00:00+00:00",
            "latest_published": "2026-07-10T10:45:00.250000+00:00",
            "source_count": 2,
            "article_count": 3,
            "sources": [
                {
                    "source": "Outlet One",
                    "slug": "test-one",
                    "title": "Bridge closes for repairs",
                    "url": "https://news.test/g1",
                    "published": "2026-07-10T10:00:00+00:00",
                },
                {
                    "source": "Outlet Two",
                    "slug": "test-two",
                    "title": "Bridge closure begins",
                    "url": "https://news.test/g2",
                    "published": "2026-07-10T10:30:00+00:00",
                },
            ],
        },
    ],
}
EXPECTED_NEWS_SOURCES = {
    "sources": [
        {
            "slug": "test-one",
            "name": "Outlet One",
            "homepage": "https://one.test",
            "enabled": True,
            "category": "sports",
            "last_fetch": "2026-07-10T10:05:30.250000+00:00",
            "last_status": "ok (3 entries, 1 changed)",
            "article_count": 2,
        },
        {
            "slug": "test-one",
            "name": "Outlet One",
            "homepage": "https://one.test",
            "enabled": True,
            "category": "news",
            "last_fetch": None,
            "last_status": None,
            "article_count": 2,
        },
        {
            "slug": "test-two",
            "name": "Outlet Two",
            "homepage": "https://two.test",
            "enabled": True,
            "category": "news",
            "last_fetch": "2026-07-10T10:00:00+00:00",
            "last_status": "error (HTTP 404)",
            "article_count": 2,
        },
    ]
}
EXPECTED_EVENTS = {
    "count": 3,
    "origin": {"lat": 35.0456, "lon": -85.3097},
    "items": [
        {
            "id": 1,
            "title": "test-Jazz Night",
            "description": "Live jazz.",
            "starts_at": "2099-06-01T18:00:00+00:00",
            "ends_at": "2099-06-01T21:00:00+00:00",
            "venue_name": "The Club",
            "address": "1 Main St, Chattanooga, TN",
            "image_url": "https://img.test/jazz.jpg",
            "latitude": 35.0456,
            "longitude": -85.3097,
            "tags": ["food", "music"],
            "links": [
                {"source_name": "test-a", "source_url": "https://a.test/jazz"},
                {"source_name": "test-b", "source_url": "https://b.test/jazz"},
            ],
            "distance_miles": 0.0,
        },
        {
            "id": 2,
            "title": "test-Far Fair",
            "description": "",
            "starts_at": "2099-06-02T18:00:00+00:00",
            "ends_at": None,
            "venue_name": None,
            "address": None,
            "image_url": None,
            "latitude": 35.2,
            "longitude": -85.1,
            "tags": ["food"],
            "links": [{"source_name": "test-a", "source_url": "https://a.test/fair"}],
            "distance_miles": 15.9,
        },
        {
            "id": 3,
            "title": "test-Unlocated Talk",
            "description": "",
            "starts_at": "2099-06-03T18:00:00.000005+00:00",
            "ends_at": None,
            "venue_name": None,
            "address": None,
            "image_url": None,
            "latitude": None,
            "longitude": None,
            "tags": [],
            "links": [],
            "distance_miles": None,
        },
    ],
}
EXPECTED_WEATHER = {
    "current": {
        "temperature_f": 89,
        "description": "Partly Cloudy",
        "icon": "https://api.weather.gov/icons/land/day/sct?size=medium",
        "wind_mph": None,
        "wind_direction": "SW",
        "humidity_percent": 58,
        "observed_at": "2026-07-16T14:53:00+00:00",
    },
    "periods": [
        {
            "name": "Today",
            "temperature": 92,
            "temperature_unit": "F",
            "precip_percent": 20,
            "short_forecast": "Mostly Sunny",
            "detailed_forecast": "Mostly sunny, with a high near 92. Southwest wind 5 to 10 mph. "
            "Chance of precipitation is 20%.",
        },
        {
            "name": "Tonight",
            "temperature": 71,
            "temperature_unit": "F",
            "precip_percent": None,
            "short_forecast": "Mostly Clear",
            "detailed_forecast": "Mostly clear, with a low around 71. South wind around 5 mph.",
        },
    ],
    "aqi": {
        "value": 62,
        "category": 2,
        "category_name": "Moderate",
        "pollutant": "PM2.5",
        "observed_at": "2026-11-06T22:00:00-05:00",
    },
}


# --- documentation models and OpenAPI -------------------------------------------
# Appended after the golden tests above, which stay byte-identical.


async def test_entities_response_matches_documentation_model(client, db_session):
    from app.geojson import EntityFeatureCollection

    await _seed_timeseries(db_session)
    for params in ({"source": "test-golden"}, {"source": "test-golden", "active": "false"}):
        body = (await client.get("/api/v1/timeseries/entities", params=params)).json()
        doc = EntityFeatureCollection.model_validate(body)
        assert len(doc.features) == 1
        # Round-trips to the same JSON: nothing dropped, extra keys kept.
        assert doc.model_dump(mode="json") == body
    assert doc.features[0].properties.model_extra == {"units": ["E1", "L2"]}


async def test_observations_response_matches_documentation_model(client, db_session):
    from app.geojson import ObservationFeatureCollection

    await _seed_timeseries(db_session)
    r = await client.get("/api/v1/timeseries/observations", params={"source": "test-golden"})
    body = r.json()
    doc = ObservationFeatureCollection.model_validate(body)
    assert len(doc.features) == 4
    assert doc.model_dump(mode="json") == body


def test_every_api_route_documents_a_named_200_schema():
    schema = app.openapi()
    checked = []
    no_content = []
    for path, ops in schema["paths"].items():
        if not path.startswith("/api/v1/"):
            continue
        for method, op in ops.items():
            if "200" not in op["responses"]:
                # Body-less 204 routes carry no JSON schema to document.
                assert "204" in op["responses"], f"{method.upper()} {path}"
                no_content.append(f"{method.upper()} {path}")
                continue
            content = op["responses"]["200"]["content"]["application/json"]["schema"]
            if content.get("type") == "array":  # /track and /sources are JSON arrays
                content = content["items"]
            assert "$ref" in content, f"{method.upper()} {path}: {content}"
            assert content["$ref"].startswith("#/components/schemas/")
            checked.append(f"{method.upper()} {path}")
    # Every JSON route, refresh routes included (the WebSocket is not in OpenAPI).
    assert len(checked) == 15, checked
    assert no_content == ["POST /api/v1/auth/login", "POST /api/v1/auth/logout"]
