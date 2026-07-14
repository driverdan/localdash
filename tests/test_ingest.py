"""Tests for the ingestion service.

`state_changed` is tested purely (no DB). The full upsert/append/closure flow is
tested against a real Postgres+PostGIS+TimescaleDB if DATABASE_URL is reachable,
otherwise skipped (e.g. local dev without the DB container running).
"""

from __future__ import annotations

from sqlalchemy import func, select

from app.collectors.base import NormalizedObservation
from app.ingest import ingest, state_changed
from app.models import Entity, Observation

# --- pure change-detection rule -------------------------------------------------


# Change detection now compares (status, geometry fingerprint) rather than raw
# lat/lon movement; see geom_fingerprint() and test_ingest_helpers.py.


def test_state_changed_status_transition():
    assert state_changed("Queued", "fp", True, "Enroute", "fp")


def test_state_unchanged_when_identical():
    assert not state_changed("Enroute", "fp", True, "Enroute", "fp")


def test_state_changed_on_geometry_change():
    assert state_changed("Enroute", "fpA", True, "Enroute", "fpB")


def test_state_changed_when_reappeared():
    assert state_changed("Closed", "fp", False, "Queued", "fp")


def test_state_unchanged_when_fingerprint_stable():
    assert not state_changed("Enroute", "fp", True, "Enroute", "fp")


# --- full DB-backed flow --------------------------------------------------------


def _obs(ext, status, lat=35.0, lon=-85.0, **props):
    return NormalizedObservation(
        external_id=ext,
        category="police",
        label="Test",
        lat=lat,
        lon=lon,
        status=status,
        properties={"status": status, **props},
    )


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


_RING = [[-85.0, 35.0], [-85.0, 35.1], [-84.9, 35.1], [-84.9, 35.0], [-85.0, 35.0]]


def _poly_obs(ext, status, ring=_RING, **props):
    return NormalizedObservation(
        external_id=ext,
        category="general",
        label="Advisory",
        geometry={"type": "Polygon", "coordinates": [ring]},
        status=status,
        properties={"status": status, **props},
    )


async def test_ingest_polygon_geometry(db_session):
    # A polygon source ingests with polygon geometry stored (not a point).
    diff = await ingest(db_session, "test", [_poly_obs("a1", "Planned Work")])
    assert len(diff.new) == 1
    assert diff.new[0]["geometry"]["type"] == "Polygon"

    ent = await _entity(db_session, "a1", "test")
    geom_type = (
        await db_session.execute(
            select(func.ST_GeometryType(Entity.last_geom)).where(Entity.id == ent.id)
        )
    ).scalar_one()
    assert geom_type == "ST_Polygon"
    assert ent.geom_fingerprint  # fingerprint recorded for change detection

    # Same advisory, unchanged status + shape -> no new observation.
    diff = await ingest(db_session, "test", [_poly_obs("a1", "Planned Work")])
    assert not diff.updated
    assert await _count(db_session, Observation, "test") == 1

    # Reshaped affected area -> new observation even with unchanged status.
    bigger = [[-85.0, 35.0], [-85.0, 35.3], [-84.7, 35.3], [-84.7, 35.0], [-85.0, 35.0]]
    diff = await ingest(db_session, "test", [_poly_obs("a1", "Planned Work", ring=bigger)])
    assert len(diff.updated) == 1
    assert await _count(db_session, Observation, "test") == 2


async def _count(session, model, source_key: str = "test") -> int:
    return (
        await session.execute(
            select(func.count()).select_from(model.__table__).where(model.source_key == source_key)
        )
    ).scalar_one()


async def _entity(session, external_id: str, source_key: str = "test") -> Entity:
    return (
        await session.execute(
            select(Entity).where(Entity.source_key == source_key, Entity.external_id == external_id)
        )
    ).scalar_one()
