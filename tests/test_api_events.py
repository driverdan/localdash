"""DB-backed tests for the /api/v1/events handlers.

Handlers are called directly with a real session (same auto-skip pattern as
the other DB suites). Seeded titles/addresses/sources are 'test-' prefixed so
the fixture cleans them and assertions can scope to them via search.
"""
from __future__ import annotations

import datetime as dt

from app.api.events import items, refresh, tags
from app.events.ingest import upsert_raw_events
from app.events.sources.base import RawEvent
from tests.fakes import FakeGeocoder

UTC = dt.timezone.utc
CENTER = (35.0456, -85.3097)  # geocode target = the default origin -> 0 miles
NASHVILLE = (36.1627, -86.7816)  # ~110 miles away


def _raw(title, starts_in_days, address=None):
    now = dt.datetime.now(UTC)
    return RawEvent(
        title=title,
        start_time=now + dt.timedelta(days=starts_in_days),
        source_name="test-api",
        source_url="http://test-api/event",
        address=address,
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
    result = await items(search="test-", session=events_db_session)

    assert [i["title"] for i in result["items"]] == [
        "test-Near Jazz Show",
        "test-Far Rock Concert",
        "test-Unlocated Poetry Reading",
    ]
    assert result["count"] == 3
    assert result["origin"] == {"lat": CENTER[0], "lon": CENTER[1]}

    by_title = {i["title"]: i for i in result["items"]}
    assert by_title["test-Near Jazz Show"]["distance_miles"] == 0.0
    assert by_title["test-Far Rock Concert"]["distance_miles"] > 100
    assert by_title["test-Unlocated Poetry Reading"]["distance_miles"] is None
    assert by_title["test-Unlocated Poetry Reading"]["latitude"] is None
    assert by_title["test-Near Jazz Show"]["links"] == [
        {"source_name": "test-api", "source_url": "http://test-api/event"}
    ]


async def test_upcoming_false_includes_past_events(events_db_session):
    await _seed(events_db_session)
    result = await items(search="test-", upcoming=False, session=events_db_session)
    assert result["count"] == 4
    assert result["items"][0]["title"] == "test-Past Gala Dinner"


async def test_distance_filter_excludes_far_and_unlocated(events_db_session):
    await _seed(events_db_session)
    result = await items(search="test-", max_miles=15, session=events_db_session)
    assert [i["title"] for i in result["items"]] == ["test-Near Jazz Show"]


async def test_topic_filter_matches_any_requested_tag(events_db_session):
    await _seed(events_db_session)
    result = await items(search="test-", topic=["music"], session=events_db_session)
    assert {i["title"] for i in result["items"]} == {
        "test-Near Jazz Show",  # "jazz" -> music
        "test-Far Rock Concert",  # "concert" -> music
    }

    result = await items(
        search="test-", topic=["food"], upcoming=False, session=events_db_session
    )
    assert {i["title"] for i in result["items"]} == {"test-Past Gala Dinner"}  # "dinner" -> food


async def test_title_search(events_db_session):
    await _seed(events_db_session)
    result = await items(search="jazz", session=events_db_session)
    assert "test-Near Jazz Show" in {i["title"] for i in result["items"]}
    assert "test-Far Rock Concert" not in {i["title"] for i in result["items"]}


async def test_tags_endpoint_lists_known_tags_sorted(events_db_session):
    await _seed(events_db_session)
    result = await tags(session=events_db_session)
    assert {"food", "music"} <= set(result["tags"])
    assert result["tags"] == sorted(result["tags"])


async def test_refresh_endpoint_reports_counts(events_db_session, monkeypatch):
    # Endpoint contract only: an empty registry refresh reports zero counts.
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
    result = await refresh()
    # The reconciliation pass runs against whatever upcoming events the shared
    # DB holds, so its count is asserted for presence rather than a value.
    assert result["reconciled"] >= 0
    assert {k: result[k] for k in ("created", "merged", "skipped_far", "retried", "resolved")} == {
        "created": 0,
        "merged": 0,
        "skipped_far": 0,
        "retried": 0,
        "resolved": 0,
    }
