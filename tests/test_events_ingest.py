"""DB-backed tests for the events ingest pipeline (ported from the PoC).

Uses the events_db_session fixture (auto-skips without a reachable Postgres).
Source names and addresses are 'test-' prefixed so the fixture can clean up
without touching real rows.
"""
import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.events.ingest import run_sources, upsert_raw_events
from app.events.models import Event, EventLink, GeocodeCache
from app.events.sources.base import RawEvent
from tests.fakes import BrokenSource, FakeGeocoder, FakeSource

UTC = dt.timezone.utc
BROAD_ST = "test-1 Broad St, Chattanooga, TN"
MARKET_ST = "test-100 Market St, Chattanooga, TN"


def make_raw(source, title="Jazz Night", **overrides):
    base = dict(
        title=title,
        start_time=dt.datetime(2026, 7, 1, 19, 0, tzinfo=UTC),
        source_name=source,
        source_url=f"http://{source}/event",
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

    assert stats == {"created": 1, "merged": 1}
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
            select(func.ST_Y(Event.location), func.ST_X(Event.location)).where(
                Event.id == event.id
            )
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
