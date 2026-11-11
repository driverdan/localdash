"""DB-backed tests for the /api/v1/events handlers.

Handlers are called directly with a session on the suite's temporary
database, emptied before each test (see conftest.py), so listings contain only
what each test seeds.
"""

from __future__ import annotations

import datetime as dt

from app.api.events import items, refresh, tags
from app.events.ingest import upsert_raw_events
from app.events.schemas import EventsRefreshResult, UpsertStats
from app.events.sources.base import RawEvent
from tests.conftest import make_settings
from tests.fakes import FakeGeocoder

UTC = dt.timezone.utc
CENTER = (35.0456, -85.3097)  # geocode target = the default origin -> 0 miles
NASHVILLE = (36.1627, -86.7816)  # ~110 miles away


def _raw(title, starts_in_days, address=None, image_url=None, ends_in_days=None):
    now = dt.datetime.now(UTC)
    return RawEvent(
        title=title,
        start_time=now + dt.timedelta(days=starts_in_days),
        end_time=now + dt.timedelta(days=ends_in_days) if ends_in_days is not None else None,
        source_name="test-api",
        source_url="http://test-api/event",
        address=address,
        image_url=image_url,
    )


async def _seed(session):
    geo = FakeGeocoder({"test-near": CENTER, "test-far": NASHVILLE})
    await upsert_raw_events(
        session,
        [
            _raw("test-Near Jazz Show", 1, address="test-near"),
            _raw("test-Far Rock Concert", 2, address="test-far"),
            _raw("test-Unlocated Poetry Reading", 3),
            _raw("test-Past Gala Dinner", -2, address="test-near"),
        ],
        geo,
    )


async def test_default_listing_is_upcoming_in_start_order(events_db_session):
    await _seed(events_db_session)
    result = await items(session=events_db_session, settings=make_settings())

    assert [i.title for i in result.items] == [
        "test-Near Jazz Show",
        "test-Far Rock Concert",
        "test-Unlocated Poetry Reading",
    ]
    assert result.count == 3
    assert result.origin.model_dump() == {"lat": CENTER[0], "lon": CENTER[1]}

    by_title = {i.title: i for i in result.items}
    assert by_title["test-Near Jazz Show"].distance_miles == 0.0
    assert by_title["test-Far Rock Concert"].distance_miles > 100
    assert by_title["test-Unlocated Poetry Reading"].distance_miles is None
    assert by_title["test-Unlocated Poetry Reading"].latitude is None
    assert [link.model_dump() for link in by_title["test-Near Jazz Show"].links] == [
        {"source_name": "test-api", "source_url": "http://test-api/event"}
    ]


async def test_default_listing_keeps_in_progress_events(events_db_session):
    # upcoming means "not yet ended": an event that started but whose end time
    # is still in the future stays listed; an ended event drops out; a started
    # event without an end time drops out (no end time is invented).
    await upsert_raw_events(
        events_db_session,
        [
            _raw("test-In Progress Show", starts_in_days=-1, ends_in_days=1),
            _raw("test-Ended Show", starts_in_days=-2, ends_in_days=-1),
            _raw("test-Started No End Show", starts_in_days=-1),
        ],
        FakeGeocoder({}),
    )
    result = await items(session=events_db_session, settings=make_settings())
    assert {i.title for i in result.items} == {"test-In Progress Show"}


async def test_listing_serializes_image_url(events_db_session):
    geo = FakeGeocoder({})
    await upsert_raw_events(
        events_db_session,
        [
            _raw("test-Imaged Show", 1, image_url="http://img.test/show.jpg"),
            _raw("test-Imageless Show", 2),
        ],
        geo,
    )
    result = await items(session=events_db_session, settings=make_settings())
    by_title = {i.title: i for i in result.items}
    assert by_title["test-Imaged Show"].image_url == "http://img.test/show.jpg"
    assert by_title["test-Imageless Show"].image_url is None


async def test_upcoming_false_includes_past_events(events_db_session):
    await _seed(events_db_session)
    result = await items(upcoming=False, session=events_db_session, settings=make_settings())
    assert result.count == 4
    assert result.items[0].title == "test-Past Gala Dinner"


async def test_distance_filter_excludes_far_and_unlocated(events_db_session):
    await _seed(events_db_session)
    result = await items(max_miles=15, session=events_db_session, settings=make_settings())
    assert [i.title for i in result.items] == ["test-Near Jazz Show"]


async def test_topic_filter_matches_any_requested_tag(events_db_session):
    await _seed(events_db_session)
    result = await items(topic=["music"], session=events_db_session, settings=make_settings())
    assert {i.title for i in result.items} == {
        "test-Near Jazz Show",  # "jazz" -> music
        "test-Far Rock Concert",  # "concert" -> music
    }

    result = await items(
        topic=["food"], upcoming=False, session=events_db_session, settings=make_settings()
    )
    assert {i.title for i in result.items} == {"test-Past Gala Dinner"}  # "dinner" -> food


async def test_title_search(events_db_session):
    await _seed(events_db_session)
    result = await items(search="jazz", session=events_db_session, settings=make_settings())
    assert [i.title for i in result.items] == ["test-Near Jazz Show"]


async def test_tags_endpoint_lists_known_tags_sorted(events_db_session):
    await _seed(events_db_session)
    result = await tags(session=events_db_session)
    assert result.tags == ["food", "music"]  # jazz/concert -> music, dinner -> food; sorted


async def _seed_duplicate_pair(session):
    """Two stored upcoming rows the reconciliation pass merges into one."""
    from app.events.dedup import canonical_key
    from app.events.models import Event, EventLink

    start = (dt.datetime.now(UTC) + dt.timedelta(days=7)).replace(
        hour=22, minute=0, second=0, microsecond=0
    )
    for i, title in enumerate(
        ("test-Sonic Machines Cruise In", "test-Sonic Machines Sonic Night Cruise In")
    ):
        session.add(
            Event(
                canonical_key=canonical_key(title, start),
                title=title,
                description="",
                starts_at=start,
                venue_name="Sonic",
                tags=[],
                links=[EventLink(source_name="test-seed", source_url=f"http://test-seed/{i}")],
            )
        )
    await session.commit()


async def test_refresh_endpoint_reports_counts(events_db_session, monkeypatch):
    # Endpoint contract: an empty registry refresh fetches nothing, and the
    # reconciliation pass reports the one seeded upcoming duplicate pair.
    # The registry is pinned empty because the always-on CarCruiseFinder
    # scraper would otherwise hit the live site here (registry behavior is
    # covered in test_events_meetup / test_events_carcruisefinder), and the
    # geocode retry pass is disabled so it never geocodes real cached
    # failures over the network.
    from app.config import Settings

    monkeypatch.setattr(
        "app.events.refresh.get_settings",
        lambda: Settings(_env_file=None, events_ical_feeds="", events_geocode_retry_hours=0),
    )
    monkeypatch.setattr("app.events.refresh.build_sources", lambda settings: [])
    await _seed_duplicate_pair(events_db_session)
    result = await refresh()
    assert result == EventsRefreshResult(
        created=0, merged=0, skipped_far=0, retried=0, resolved=0, reconciled=1
    )


async def test_refresh_forwards_configured_blocklist_and_center(events_db_session, monkeypatch):
    # refresh() is the composition root: it reads the settings and passes the
    # blocklist and center down to run_sources, which never reads them itself.
    from app.events import refresh as events_refresh

    settings = make_settings(
        events_ical_feeds="",
        events_geocode_retry_hours=0,
        events_blocked_tags="test-blocked, Test-Other",
        center_lat=36.5,
        center_lon=-84.25,
        events_ingest_max_miles=42,
    )
    monkeypatch.setattr("app.events.refresh.get_settings", lambda: settings)
    monkeypatch.setattr("app.events.refresh.build_sources", lambda settings: [])
    captured: dict = {}

    async def fake_run_sources(session, sources, geocoder=None, max_miles=0, **kwargs):
        captured.update(kwargs, max_miles=max_miles)
        return UpsertStats(created=0, merged=0, skipped_far=0)

    monkeypatch.setattr(events_refresh, "run_sources", fake_run_sources)
    await events_refresh.refresh()

    assert captured == {
        "max_miles": 42,
        "blocked_tags": {"test-blocked", "test-other"},
        "center": (36.5, -84.25),
    }
