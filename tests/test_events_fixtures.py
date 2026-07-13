"""Offline tests for the local fixtures source (pure expansion, no network, no DB)."""
import datetime as dt

import pytest
from dateutil.rrule import MONTHLY, SU, rrule

from app.config import Settings
from app.events.sources import build_sources
from app.events.sources.fixtures import (
    FIXTURES,
    Fixture,
    FixturesSource,
    expand,
    is_stale,
)

UTC = dt.timezone.utc


def make_fixture(**overrides) -> Fixture:
    base = dict(
        slug="test-meet",
        title="Test Meet",
        description="A test car meet.",
        venue_name="Test Venue",
        address="1 Test St, Chattanooga, TN",
        source_url="https://example.com/test-meet",
        starts=dt.time(8, 0),
        ends=dt.time(12, 0),
        rule=rrule(MONTHLY, byweekday=SU(3), bymonth=tuple(range(3, 12)), dtstart=dt.datetime(2024, 1, 1)),
    )
    base.update(overrides)
    return Fixture(**base)


def test_rrule_expansion_yields_third_sundays_in_window():
    events = expand(
        make_fixture(),
        dt.datetime(2026, 7, 1, tzinfo=UTC),
        dt.datetime(2026, 9, 29, tzinfo=UTC),
    )

    # 3rd Sundays: Jul 19, Aug 16, Sep 20 (2026), all EDT (-4) -> 12:00Z.
    assert [e.start_time for e in events] == [
        dt.datetime(2026, 7, 19, 12, 0, tzinfo=UTC),
        dt.datetime(2026, 8, 16, 12, 0, tzinfo=UTC),
        dt.datetime(2026, 9, 20, 12, 0, tzinfo=UTC),
    ]
    for e in events:
        assert e.title == "Test Meet"
        assert e.venue_name == "Test Venue"
        assert e.address == "1 Test St, Chattanooga, TN"
        assert e.source_url == "https://example.com/test-meet"
        assert e.end_time - e.start_time == dt.timedelta(hours=4)


def test_out_of_season_window_is_empty():
    events = expand(
        make_fixture(),
        dt.datetime(2026, 12, 1, tzinfo=UTC),
        dt.datetime(2027, 2, 28, tzinfo=UTC),
    )
    assert events == []


def test_dst_transition_keeps_local_wall_clock():
    # November 2026: DST ends Nov 1. October 3rd Sunday is EDT, November's EST.
    events = expand(
        make_fixture(),
        dt.datetime(2026, 10, 1, tzinfo=UTC),
        dt.datetime(2026, 11, 30, tzinfo=UTC),
    )
    assert [e.start_time for e in events] == [
        dt.datetime(2026, 10, 18, 12, 0, tzinfo=UTC),  # 8am EDT
        dt.datetime(2026, 11, 15, 13, 0, tzinfo=UTC),  # 8am EST
    ]


def test_explicit_dates_emit_one_event_per_day():
    fixture = make_fixture(
        rule=None,
        dates=(dt.date(2026, 1, 9), dt.date(2026, 1, 10), dt.date(2026, 1, 11)),
        starts=dt.time(10, 0),
        ends=dt.time(18, 0),
    )
    events = expand(
        fixture, dt.datetime(2026, 1, 1, tzinfo=UTC), dt.datetime(2026, 2, 1, tzinfo=UTC)
    )

    assert len(events) == 3
    # 10am EST -> 15:00Z, per-day starts.
    assert [e.start_time for e in events] == [
        dt.datetime(2026, 1, 9, 15, 0, tzinfo=UTC),
        dt.datetime(2026, 1, 10, 15, 0, tzinfo=UTC),
        dt.datetime(2026, 1, 11, 15, 0, tzinfo=UTC),
    ]
    assert all(e.end_time - e.start_time == dt.timedelta(hours=8) for e in events)

    # Entirely out-of-window dates emit nothing.
    assert (
        expand(fixture, dt.datetime(2026, 3, 1, tzinfo=UTC), dt.datetime(2026, 4, 1, tzinfo=UTC))
        == []
    )


def test_source_event_ids_are_deterministic_and_slug_dated():
    window = (dt.datetime(2026, 7, 1, tzinfo=UTC), dt.datetime(2026, 9, 29, tzinfo=UTC))
    first = expand(make_fixture(), *window)
    second = expand(make_fixture(), *window)

    assert [e.source_event_id for e in first] == [e.source_event_id for e in second]
    assert [e.source_event_id for e in first] == [
        "test-meet-2026-07-19",
        "test-meet-2026-08-16",
        "test-meet-2026-09-20",
    ]


def test_is_stale_with_injected_clocks():
    past_only = make_fixture(rule=None, dates=(dt.date(2026, 1, 9),))
    now = dt.datetime(2026, 7, 12, tzinfo=UTC)

    assert is_stale(past_only, now) is True
    assert is_stale(make_fixture(), now) is False  # active rrule always recurs


def test_fixture_requires_exactly_one_recurrence_form():
    with pytest.raises(ValueError):
        make_fixture(rule=None, dates=())
    with pytest.raises(ValueError):
        make_fixture(dates=(dt.date(2026, 1, 9),))  # rule also set by default


def test_seeded_registry_is_well_formed():
    slugs = [f.slug for f in FIXTURES]
    assert len(slugs) == len(set(slugs))
    for fixture in FIXTURES:
        assert fixture.title and fixture.address and fixture.source_url
        assert (fixture.rule is None) != (not fixture.dates)


def test_seeded_flagship_meet_expands_in_season():
    # Spec scenario: an in-season horizon emits the flagship monthly meet with
    # the organizer's link. Window injected so the test never depends on today.
    (cars_and_coffee,) = [f for f in FIXTURES if f.slug == "chattanooga-cars-and-coffee"]
    events = expand(
        cars_and_coffee,
        dt.datetime(2026, 8, 1, tzinfo=UTC),
        dt.datetime(2026, 8, 31, tzinfo=UTC),
    )

    (event,) = events
    assert event.title == "Chattanooga Cars and Coffee"
    assert event.venue_name == "Chattanooga State Community College"
    assert event.source_url == "https://chattanoogacarsandcoffee.com/"


async def test_fetch_emits_active_fixtures_and_warns_on_stale(caplog):
    # Clock-independent: a bare monthly rule hits any 90-day horizon, and the
    # explicit-date fixture is always past.
    active = make_fixture(
        slug="always-on",
        rule=rrule(MONTHLY, byweekday=SU(3), dtstart=dt.datetime(2024, 1, 1)),
    )
    stale = make_fixture(slug="long-gone", rule=None, dates=(dt.date(2020, 1, 1),))
    source = FixturesSource(fixtures=(active, stale))
    with caplog.at_level("WARNING", logger="localdash.events"):
        events = await source.fetch()

    assert len(events) >= 2  # ~3 monthly occurrences in 90 days
    assert all(e.source_name == "Local fixtures" for e in events)
    assert all(e.source_event_id.startswith("always-on-") for e in events)
    stale_warnings = [r for r in caplog.records if "needs review" in r.message]
    assert [r.args[0] for r in stale_warnings] == ["long-gone"]


def _settings(**overrides) -> Settings:
    base = dict(events_ical_feeds="", events_meetup_token="", events_meetup_query="")
    base.update(overrides)
    return Settings(_env_file=None, **base)


def test_build_sources_gates_fixtures_on_setting():
    assert any(isinstance(s, FixturesSource) for s in build_sources(Settings(_env_file=None)))
    assert any(isinstance(s, FixturesSource) for s in build_sources(_settings()))

    disabled = build_sources(_settings(events_fixtures_enabled=False))
    assert not any(isinstance(s, FixturesSource) for s in disabled)
    # Only the ungated CarCruiseFinder scraper remains (see test_events_meetup
    # for the full nothing-configured registry shape).