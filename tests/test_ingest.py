"""Tests for the ingestion service.

`state_changed` is tested purely (no DB). The full upsert/append/closure flow is
tested against a real Postgres+PostGIS+TimescaleDB if DATABASE_URL is reachable,
otherwise skipped (e.g. local dev without the DB container running).
"""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.collectors.base import NormalizedObservation
from app.ingest import ingest, state_changed
from app.models import Entity, Observation


# --- pure change-detection rule -------------------------------------------------

def test_state_changed_status_transition():
    assert state_changed("Queued", 35.0, -85.0, True, "Enroute", 35.0, -85.0)


def test_state_unchanged_when_identical():
    assert not state_changed("Enroute", 35.0, -85.0, True, "Enroute", 35.0, -85.0)


def test_state_changed_on_movement():
    assert state_changed("Enroute", 35.0, -85.0, True, "Enroute", 35.5, -85.0)


def test_state_changed_when_reappeared():
    assert state_changed("Closed", 35.0, -85.0, False, "Queued", 35.0, -85.0)


def test_state_unchanged_sub_epsilon_jitter():
    assert not state_changed("Enroute", 35.0, -85.0, True, "Enroute", 35.0 + 1e-9, -85.0)


# --- full DB-backed flow --------------------------------------------------------

def _obs(ext, status, lat=35.0, lon=-85.0, **props):
    return NormalizedObservation(
        external_id=ext, category="police", label="Test",
        lat=lat, lon=lon, status=status, properties={"status": status, **props},
    )


@pytest.fixture
async def db_session():
    """Async session against the real DB; skips if unreachable."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from app.config import get_settings

    engine = create_async_engine(get_settings().database_url)
    try:
        async with engine.connect() as conn:
            await conn.execute(select(1))
    except Exception as exc:  # noqa: BLE001
        await engine.dispose()
        pytest.skip(f"database not reachable: {exc}")

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        # Clean slate for the test source.
        await session.execute(
            Observation.__table__.delete().where(Observation.source_key == "test")
        )
        await session.execute(Entity.__table__.delete().where(Entity.source_key == "test"))
        await session.commit()
        yield session
    await engine.dispose()


async def test_ingest_full_lifecycle(db_session):
    # 1. First poll: two new incidents.
    diff = await ingest(db_session, "test", [_obs("1", "Queued"), _obs("2", "Enroute")])
    assert len(diff.new) == 2 and not diff.updated and not diff.closed

    obs_count = await _count(db_session, Observation)
    assert obs_count == 2

    # 2. Second poll: #1 changes status, #2 unchanged -> one updated, no new obs for #2.
    diff = await ingest(db_session, "test", [_obs("1", "Enroute"), _obs("2", "Enroute")])
    assert not diff.new
    assert len(diff.updated) == 1
    assert await _count(db_session, Observation) == 3  # only #1 appended

    # 3. Third poll: #2 disappears -> closed; #1 still present unchanged.
    diff = await ingest(db_session, "test", [_obs("1", "Enroute")])
    assert diff.closed and not diff.new
    ent2 = await _entity(db_session, "2")
    assert ent2.is_active is False
    assert await _count(db_session, Observation) == 4  # Closed obs for #2

    # 4. #2 reappears -> new observation, active again.
    diff = await ingest(db_session, "test", [_obs("1", "Enroute"), _obs("2", "Queued")])
    assert len(diff.updated) == 1
    ent2 = await _entity(db_session, "2")
    assert ent2.is_active is True


async def test_active_endpoint_include_closed(db_session):
    from app.api.routes import active

    # #1 stays active, #2 gets closed on the second poll.
    await ingest(db_session, "test", [_obs("1", "Queued"), _obs("2", "Enroute")])
    await ingest(db_session, "test", [_obs("1", "Queued")])

    # Default: only active entities.
    fc = await active(source="test", session=db_session)
    assert {f["properties"]["external_id"] for f in fc["features"]} == {"1"}

    # include_closed=True: closed entity returned, flagged inactive + status "Closed".
    fc = await active(source="test", include_closed=True, closed_within_minutes=60, session=db_session)
    by_ext = {f["properties"]["external_id"]: f["properties"] for f in fc["features"]}
    assert set(by_ext) == {"1", "2"}
    assert by_ext["1"]["active"] is True and by_ext["1"]["status"] == "Queued"
    assert by_ext["2"]["active"] is False and by_ext["2"]["status"] == "Closed"

    # A zero-minute window excludes anything closed before "now".
    fc = await active(source="test", include_closed=True, closed_within_minutes=0, session=db_session)
    assert {f["properties"]["external_id"] for f in fc["features"]} == {"1"}


async def _count(session, model) -> int:
    return (
        await session.execute(
            select(func.count()).select_from(model.__table__).where(model.source_key == "test")
        )
    ).scalar_one()


async def _entity(session, external_id: str) -> Entity:
    return (
        await session.execute(
            select(Entity).where(Entity.source_key == "test", Entity.external_id == external_id)
        )
    ).scalar_one()
