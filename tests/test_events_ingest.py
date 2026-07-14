"""DB-backed tests for the events ingest pipeline (ported from the PoC).

Uses the events_db_session fixture (auto-skips without a reachable Postgres).
Source names and addresses are 'test-' prefixed so the fixture can clean up
without touching real rows.
"""

import datetime as dt

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.events import CHATTANOOGA_CENTER
from app.events.ingest import (
    _haversine_miles,
    retry_failed_geocodes,
    run_sources,
    upsert_raw_events,
)
from app.events.models import Event, EventLink, GeocodeCache
from app.events.sources.base import RawEvent
from tests.fakes import BrokenSource, FakeGeocoder, FakeSource

UTC = dt.timezone.utc
BROAD_ST = "test-1 Broad St, Chattanooga, TN"
MARKET_ST = "test-100 Market St, Chattanooga, TN"
BEALE_ST = "test-1 Beale St, Memphis, TN"
MEMPHIS = (35.1495, -90.0490)
DOWNTOWN_CHATTANOOGA = (35.0456, -85.3097)


def make_raw(source, title="Jazz Night", **overrides):
    # URL is per-listing (title-derived slug): each distinct upstream listing
    # has its own page, and the source-listing identity tier relies on that.
    base = dict(
        title=title,
        start_time=dt.datetime(2026, 7, 1, 19, 0, tzinfo=UTC),
        source_name=source,
        source_url=f"http://{source}/event/{title.lower().replace(' ', '-')}",
        description="live jazz music concert",
    )
    base.update(overrides)
    return RawEvent(**base)


async def _events(session) -> list[Event]:
    """Only events created by this test module (a real DB may hold others)."""
    return list(
        (
            await session.scalars(
                select(Event)
                .where(Event.links.any(EventLink.source_name.like("test-%")))
                .options(selectinload(Event.links), selectinload(Event.tags))
            )
        ).all()
    )


async def test_duplicate_across_sources_merges_into_one_event(events_db_session):
    stats = await upsert_raw_events(
        events_db_session, [make_raw("test-SourceA"), make_raw("test-SourceB")]
    )

    assert stats == {"created": 1, "merged": 1, "skipped_far": 0}
    events = await _events(events_db_session)
    assert len(events) == 1
    assert {link.source_name for link in events[0].links} == {"test-SourceA", "test-SourceB"}
    assert "music" in {tag.name for tag in events[0].tags}


async def test_distinct_events_are_kept_separate(events_db_session):
    await upsert_raw_events(
        events_db_session,
        [
            make_raw("test-SourceA", title="Jazz Night"),
            make_raw(
                "test-SourceA",
                title="Rock Show",
                start_time=dt.datetime(2026, 7, 2, 20, 0, tzinfo=UTC),
            ),
        ],
    )
    assert len(await _events(events_db_session)) == 2


async def test_re_ingesting_same_source_does_not_duplicate_links(events_db_session):
    await upsert_raw_events(events_db_session, [make_raw("test-SourceA")])
    await upsert_raw_events(events_db_session, [make_raw("test-SourceA")])
    (event,) = await _events(events_db_session)
    assert len(event.links) == 1


async def test_merge_backfills_missing_fields(events_db_session):
    geo = FakeGeocoder({BROAD_ST: (35.0556, -85.3110)})
    await upsert_raw_events(events_db_session, [make_raw("test-SourceA")], geo)
    (event,) = await _events(events_db_session)
    assert event.address is None and event.location is None

    # A second source supplies the address -> backfilled and geocoded.
    await upsert_raw_events(
        events_db_session,
        [make_raw("test-SourceB", venue_name="The Spot", address=BROAD_ST)],
        geo,
    )
    (event,) = await _events(events_db_session)
    assert event.address == BROAD_ST
    assert event.venue_name == "The Spot"
    assert event.location is not None


async def test_run_sources_persists_and_tolerates_failures(events_db_session):
    stats = await run_sources(
        events_db_session, [FakeSource([make_raw("test-fake")]), BrokenSource()]
    )
    assert stats["created"] == 1
    assert len(await _events(events_db_session)) == 1


async def test_address_is_geocoded_to_coordinates(events_db_session):
    geo = FakeGeocoder({BROAD_ST: (35.0556, -85.3110)})
    await upsert_raw_events(events_db_session, [make_raw("test-SourceA", address=BROAD_ST)], geo)

    (event,) = await _events(events_db_session)
    lat, lon = (
        await events_db_session.execute(
            select(func.ST_Y(Event.location), func.ST_X(Event.location)).where(Event.id == event.id)
        )
    ).one()
    assert (round(lat, 4), round(lon, 4)) == (35.0556, -85.3110)


async def test_geocoder_called_once_per_address_within_a_run(events_db_session):
    geo = FakeGeocoder({BROAD_ST: (35.0556, -85.3110)})
    # Same event reported by two sources -> one geocode.
    await upsert_raw_events(
        events_db_session,
        [
            make_raw("test-SourceA", address=BROAD_ST),
            make_raw("test-SourceB", address=BROAD_ST),
        ],
        geo,
    )
    assert geo.calls.count(BROAD_ST) == 1


async def test_geocode_results_cached_in_db_across_runs(events_db_session):
    geo = FakeGeocoder({MARKET_ST: (35.05, -85.31)})

    await upsert_raw_events(
        events_db_session, [make_raw("test-SourceA", title="Show One", address=MARKET_ST)], geo
    )
    # A different event at the same address in a later run must reuse the cache.
    await upsert_raw_events(
        events_db_session,
        [
            make_raw(
                "test-SourceA",
                title="Show Two",
                start_time=dt.datetime(2026, 8, 1, 20, 0, tzinfo=UTC),
                address=MARKET_ST,
            )
        ],
        geo,
    )

    events = await _events(events_db_session)
    assert len(events) == 2
    assert geo.calls.count(MARKET_ST) == 1
    cached = (
        await events_db_session.scalars(
            select(GeocodeCache).where(GeocodeCache.address == MARKET_ST)
        )
    ).all()
    assert len(cached) == 1
    assert all(e.location is not None for e in events)


async def test_unresolvable_address_is_recorded_and_not_retried(events_db_session):
    geo = FakeGeocoder({})  # resolves nothing

    await upsert_raw_events(
        events_db_session, [make_raw("test-SourceA", title="A", address="test-Nowhere")], geo
    )
    await upsert_raw_events(
        events_db_session,
        [
            make_raw(
                "test-SourceA",
                title="B",
                start_time=dt.datetime(2026, 9, 1, 20, 0, tzinfo=UTC),
                address="test-Nowhere",
            )
        ],
        geo,
    )

    # Geocoder attempted only once; the null result is cached.
    assert geo.calls.count("test-Nowhere") == 1
    cached = await events_db_session.scalar(
        select(GeocodeCache).where(GeocodeCache.address == "test-Nowhere")
    )
    assert cached.latitude is None and cached.longitude is None


def test_haversine_known_distance_and_zero():
    assert _haversine_miles(CHATTANOOGA_CENTER, MEMPHIS) == pytest.approx(268, abs=10)
    assert _haversine_miles(MEMPHIS, MEMPHIS) == 0


async def test_far_new_event_is_dropped_and_counted(events_db_session):
    geo = FakeGeocoder({BEALE_ST: MEMPHIS})
    stats = await upsert_raw_events(
        events_db_session, [make_raw("test-SourceA", address=BEALE_ST)], geo, max_miles=100
    )

    assert stats == {"created": 0, "merged": 0, "skipped_far": 1}
    assert await _events(events_db_session) == []
    links = (
        await events_db_session.scalars(
            select(EventLink).where(EventLink.source_name == "test-SourceA")
        )
    ).all()
    assert links == []


async def test_nearby_new_event_passes_the_filter(events_db_session):
    geo = FakeGeocoder({BROAD_ST: DOWNTOWN_CHATTANOOGA})
    stats = await upsert_raw_events(
        events_db_session, [make_raw("test-SourceA", address=BROAD_ST)], geo, max_miles=100
    )

    assert stats == {"created": 1, "merged": 0, "skipped_far": 0}
    (event,) = await _events(events_db_session)
    assert event.location is not None


async def test_unlocated_events_are_kept_when_filter_is_on(events_db_session):
    geo = FakeGeocoder({})  # every lookup fails
    stats = await upsert_raw_events(
        events_db_session,
        [
            make_raw("test-SourceA", title="No Address"),
            make_raw("test-SourceA", title="Bad Address", address="test-Nowhere Far"),
        ],
        geo,
        max_miles=100,
    )

    assert stats == {"created": 2, "merged": 0, "skipped_far": 0}
    events = await _events(events_db_session)
    assert len(events) == 2
    assert all(e.location is None for e in events)


async def test_zero_max_miles_disables_the_filter(events_db_session):
    geo = FakeGeocoder({BEALE_ST: MEMPHIS})
    stats = await upsert_raw_events(
        events_db_session, [make_raw("test-SourceA", address=BEALE_ST)], geo, max_miles=0
    )

    assert stats == {"created": 1, "merged": 0, "skipped_far": 0}
    (event,) = await _events(events_db_session)
    assert event.location is not None


async def test_merge_path_is_exempt_from_the_filter(events_db_session):
    geo = FakeGeocoder({BROAD_ST: DOWNTOWN_CHATTANOOGA, BEALE_ST: MEMPHIS})
    await upsert_raw_events(
        events_db_session, [make_raw("test-SourceA", address=BROAD_ST)], geo, max_miles=100
    )
    # Same canonical key from a second source, even with a far address, merges.
    stats = await upsert_raw_events(
        events_db_session, [make_raw("test-SourceB", address=BEALE_ST)], geo, max_miles=100
    )

    assert stats == {"created": 0, "merged": 1, "skipped_far": 0}
    (event,) = await _events(events_db_session)
    assert {link.source_name for link in event.links} == {"test-SourceA", "test-SourceB"}


# --- geocode failure retry pass ---


async def _age_cache_row(session, address, hours):
    """Push a cache row's last attempt into the past to make it retry-eligible."""
    from sqlalchemy import update

    await session.execute(
        update(GeocodeCache)
        .where(GeocodeCache.address == address)
        .values(last_attempted_at=dt.datetime.now(UTC) - dt.timedelta(hours=hours))
    )
    await session.commit()


async def _cache_row(session, address) -> GeocodeCache:
    return await session.scalar(select(GeocodeCache).where(GeocodeCache.address == address))


async def test_stale_failure_retried_and_events_backfilled(events_db_session):
    # Ingest with a failing geocoder: cached failure + unlocated event.
    await upsert_raw_events(
        events_db_session, [make_raw("test-SourceA", address=BROAD_ST)], FakeGeocoder({})
    )
    await _age_cache_row(events_db_session, BROAD_ST, hours=48)

    retry_geo = FakeGeocoder({BROAD_ST: DOWNTOWN_CHATTANOOGA})
    stats = await retry_failed_geocodes(events_db_session, retry_geo, retry_hours=24, batch=25)

    assert stats == {"retried": 1, "resolved": 1}
    row = await _cache_row(events_db_session, BROAD_ST)
    assert (row.latitude, row.longitude) == DOWNTOWN_CHATTANOOGA
    (event,) = await _events(events_db_session)
    await events_db_session.refresh(event)
    assert event.location is not None


async def test_success_rows_are_never_requeried(events_db_session):
    await upsert_raw_events(
        events_db_session,
        [make_raw("test-SourceA", address=MARKET_ST)],
        FakeGeocoder({MARKET_ST: DOWNTOWN_CHATTANOOGA}),
    )
    await _age_cache_row(events_db_session, MARKET_ST, hours=48)

    retry_geo = FakeGeocoder({MARKET_ST: MEMPHIS})
    stats = await retry_failed_geocodes(events_db_session, retry_geo, retry_hours=24, batch=25)

    assert stats == {"retried": 0, "resolved": 0}
    assert retry_geo.calls == []
    row = await _cache_row(events_db_session, MARKET_ST)
    assert (row.latitude, row.longitude) == DOWNTOWN_CHATTANOOGA


async def test_fresh_failure_waits_out_the_age_window(events_db_session):
    await upsert_raw_events(
        events_db_session, [make_raw("test-SourceA", address=BROAD_ST)], FakeGeocoder({})
    )  # last_attempted_at = now

    retry_geo = FakeGeocoder({BROAD_ST: DOWNTOWN_CHATTANOOGA})
    stats = await retry_failed_geocodes(events_db_session, retry_geo, retry_hours=24, batch=25)

    assert stats == {"retried": 0, "resolved": 0}
    assert retry_geo.calls == []


async def test_failed_retry_bumps_last_attempt(events_db_session):
    await upsert_raw_events(
        events_db_session, [make_raw("test-SourceA", address=BROAD_ST)], FakeGeocoder({})
    )
    await _age_cache_row(events_db_session, BROAD_ST, hours=48)
    before = (await _cache_row(events_db_session, BROAD_ST)).last_attempted_at

    still_failing = FakeGeocoder({})
    stats = await retry_failed_geocodes(events_db_session, still_failing, retry_hours=24, batch=25)
    assert stats == {"retried": 1, "resolved": 0}
    after = await _cache_row(events_db_session, BROAD_ST)
    assert after.latitude is None
    assert after.last_attempted_at > before

    # Now inside the age window: not retried again.
    stats = await retry_failed_geocodes(events_db_session, still_failing, retry_hours=24, batch=25)
    assert stats == {"retried": 0, "resolved": 0}
    assert still_failing.calls == [BROAD_ST]


async def test_batch_cap_takes_oldest_first(events_db_session):
    addresses = [f"test-{i} Cap St, Chattanooga, TN" for i in range(3)]
    raws = [
        make_raw("test-SourceA", title=f"Cap Event {i}", address=addr)
        for i, addr in enumerate(addresses)
    ]
    await upsert_raw_events(events_db_session, raws, FakeGeocoder({}))
    # Ages: index 0 newest-stale (30h) ... index 2 oldest (72h).
    for i, addr in enumerate(addresses):
        await _age_cache_row(events_db_session, addr, hours=30 + i * 21)

    retry_geo = FakeGeocoder({})
    stats = await retry_failed_geocodes(events_db_session, retry_geo, retry_hours=24, batch=2)

    assert stats == {"retried": 2, "resolved": 0}
    assert retry_geo.calls == [addresses[2], addresses[1]]


async def test_non_positive_retry_hours_disables_the_pass(events_db_session):
    await upsert_raw_events(
        events_db_session, [make_raw("test-SourceA", address=BROAD_ST)], FakeGeocoder({})
    )
    await _age_cache_row(events_db_session, BROAD_ST, hours=48)

    retry_geo = FakeGeocoder({BROAD_ST: DOWNTOWN_CHATTANOOGA})
    stats = await retry_failed_geocodes(events_db_session, retry_geo, retry_hours=0, batch=25)

    assert stats == {"retried": 0, "resolved": 0}
    assert retry_geo.calls == []


# --- tiered de-duplication ---


def sonic_raws():
    """Two duplicate listings from one source, as observed upstream: subset
    titles, same start, same venue string, no address, distinct URLs."""
    start = dt.datetime(2026, 12, 3, 22, 0, tzinfo=UTC)
    return [
        make_raw(
            "test-ccf",
            title="test-Street Machines Sonic Cruise In",
            start_time=start,
            venue_name="Sonic",
            description="",
        ),
        make_raw(
            "test-ccf",
            title="test-Street Machines Cruise In",
            start_time=start,
            venue_name="Sonic",
            description="",
        ),
    ]


async def test_within_source_duplicate_listings_merge(events_db_session):
    stats = await upsert_raw_events(events_db_session, sonic_raws())

    assert stats == {"created": 1, "merged": 1, "skipped_far": 0}
    (event,) = await _events(events_db_session)
    assert len(event.links) == 2
    assert {link.source_url for link in event.links} == {
        "http://test-ccf/event/test-street-machines-sonic-cruise-in",
        "http://test-ccf/event/test-street-machines-cruise-in",
    }


async def test_merged_listings_reingest_idempotently(events_db_session):
    await upsert_raw_events(events_db_session, sonic_raws())
    stats = await upsert_raw_events(events_db_session, sonic_raws())

    assert stats == {"created": 0, "merged": 2, "skipped_far": 0}
    (event,) = await _events(events_db_session)
    assert len(event.links) == 2


async def test_fuzzy_match_requires_location_agreement(events_db_session):
    from dataclasses import replace

    bare = [replace(r, venue_name=None) for r in sonic_raws()]
    stats = await upsert_raw_events(events_db_session, bare)

    assert stats == {"created": 2, "merged": 0, "skipped_far": 0}


async def test_fuzzy_match_rejects_far_apart_coordinates(events_db_session):
    geo = FakeGeocoder({BROAD_ST: DOWNTOWN_CHATTANOOGA, BEALE_ST: MEMPHIS})
    start = dt.datetime(2026, 12, 4, 22, 0, tzinfo=UTC)
    stats = await upsert_raw_events(
        events_db_session,
        [
            make_raw(
                "test-a", title="test-Cars and Coffee Meetup", start_time=start, address=BROAD_ST
            ),
            make_raw("test-b", title="test-Cars and Coffee", start_time=start, address=BEALE_ST),
        ],
        geo,
    )

    assert stats == {"created": 2, "merged": 0, "skipped_far": 0}


async def test_recurring_listing_id_does_not_collapse_series(events_db_session):
    day1 = make_raw(
        "test-rec",
        title="test-Weekly Cruise",
        start_time=dt.datetime(2026, 12, 5, 22, 0, tzinfo=UTC),
        source_event_id="series-1",
        source_url="http://test-rec/event/weekly-cruise",
    )
    day2 = make_raw(
        "test-rec",
        title="test-Weekly Cruise",
        start_time=dt.datetime(2026, 12, 12, 22, 0, tzinfo=UTC),
        source_event_id="series-1",
        source_url="http://test-rec/event/weekly-cruise",
    )
    stats = await upsert_raw_events(events_db_session, [day1, day2])

    assert stats == {"created": 2, "merged": 0, "skipped_far": 0}
    events = await _events(events_db_session)
    assert len(events) == 2


async def test_source_listing_match_survives_retitle(events_db_session):
    original = make_raw(
        "test-src",
        title="test-Harbor Lights Festival",
        start_time=dt.datetime(2026, 12, 6, 20, 0, tzinfo=UTC),
        source_event_id="ev-9",
    )
    await upsert_raw_events(events_db_session, [original])

    retitled = make_raw(
        "test-src",
        title="test-Harbor Lights Winter Festival",
        start_time=dt.datetime(2026, 12, 6, 20, 0, tzinfo=UTC),
        source_event_id="ev-9",
    )
    stats = await upsert_raw_events(events_db_session, [retitled])

    assert stats == {"created": 0, "merged": 1, "skipped_far": 0}
    (event,) = await _events(events_db_session)
    # The retitled listing carries a new URL: both listing URLs remain.
    assert {link.source_event_id for link in event.links} == {"ev-9"}


# --- reconciliation pass ---


def seed_event(title, start, venue=None, address=None, location=None, url_slug=None):
    from app.events.dedup import canonical_key
    from app.events.models import Event

    slug = url_slug or title.lower().replace(" ", "-")
    return Event(
        canonical_key=canonical_key(title, start),
        title=title,
        description="",
        starts_at=start,
        venue_name=venue,
        address=address,
        location=location,
        tags=[],
        links=[
            EventLink(
                source_name="test-seed",
                source_url=f"http://test-seed/event/{slug}",
            )
        ],
    )


async def test_reconcile_merges_preexisting_duplicates(events_db_session):
    from app.events.ingest import reconcile_events

    start = dt.datetime(2026, 12, 8, 22, 0, tzinfo=UTC)
    keeper = seed_event("test-Sonic Machines Cruise In", start, venue="Sonic")
    dupe = seed_event("test-Sonic Machines Sonic Night Cruise In", start, venue="Sonic")
    events_db_session.add_all([keeper, dupe])
    await events_db_session.commit()

    merged = await reconcile_events(events_db_session)

    assert merged >= 1  # shared DB may hold other genuine duplicates
    (event,) = await _events(events_db_session)
    assert event.title == "test-Sonic Machines Sonic Night Cruise In"  # longer title wins
    assert len(event.links) == 2

    # Idempotent: running again leaves the surviving test event untouched.
    await reconcile_events(events_db_session)
    (again,) = await _events(events_db_session)
    assert again.id == event.id
    assert len(again.links) == 2


async def test_reconcile_merges_after_coordinates_appear(events_db_session):
    from app.events.ingest import _point, reconcile_events

    start = dt.datetime(2026, 12, 9, 22, 0, tzinfo=UTC)
    a = seed_event("test-Riverfront Cruise In", start)
    b = seed_event("test-Riverfront Sonic Cruise In", start)
    events_db_session.add_all([a, b])
    await events_db_session.commit()

    await reconcile_events(events_db_session)
    assert len(await _events(events_db_session)) == 2  # no location evidence yet

    # A later geocode resolves both addresses to the same block.
    a.location = _point(DOWNTOWN_CHATTANOOGA)
    b.location = _point((35.0457, -85.3098))
    await events_db_session.commit()

    await reconcile_events(events_db_session)
    (event,) = await _events(events_db_session)
    assert len(event.links) == 2


async def test_reconcile_merges_stale_key_exact_duplicates(events_db_session):
    # The observed "Cars & Coffee Franklin" / "Cars and Coffee Franklin" rows:
    # identical normalized titles (post stopword folding) in the same hour,
    # but stored under stale pre-folding canonical keys and geocoded just
    # past the fuzzy tier's distance gate. Key equality must merge them.
    from app.events.ingest import _point, reconcile_events

    start = dt.datetime(2026, 12, 10, 13, 0, tzinfo=UTC)
    a = seed_event("test-Karts & Koffee Franklin", start, location=_point((35.9513, -86.8840)))
    b = seed_event("test-Karts and Koffee Franklin", start, location=_point((35.9412, -86.8770)))
    # Simulate the stale stored keys: distinct, as written before the change.
    a.canonical_key = "stale-key-a"
    b.canonical_key = "stale-key-b"
    events_db_session.add_all([a, b])
    await events_db_session.commit()

    await reconcile_events(events_db_session)

    (event,) = await _events(events_db_session)
    assert len(event.links) == 2
