"""DB-backed tests for the /api/v1/timeseries handlers.

Handlers are called directly with a real session (same auto-skip pattern as
test_ingest — the db_session fixture skips if Postgres is unreachable).
Route shapes and validation are covered offline in test_api_routes.py.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.api.timeseries import entities, entity_detail, entity_track
from app.collectors.base import NormalizedObservation
from app.ingest import ingest
from app.models import Entity


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


async def _seed(session):
    """#1 stays active; #2 gets closed on the second poll."""
    await ingest(session, "test", [_obs("1", "Queued"), _obs("2", "Enroute")])
    await ingest(session, "test", [_obs("1", "Queued")])


async def _entity_id(session, external_id: str) -> int:
    return (
        await session.execute(
            select(Entity.id).where(Entity.source_key == "test", Entity.external_id == external_id)
        )
    ).scalar_one()


async def test_entities_default_active_only(db_session):
    await _seed(db_session)
    fc = await entities(source="test", session=db_session)
    assert {f["properties"]["external_id"] for f in fc["features"]} == {"1"}


async def test_entities_closed_within_includes_recently_closed(db_session):
    await _seed(db_session)
    fc = await entities(source="test", closed_within=60, session=db_session)
    by_ext = {f["properties"]["external_id"]: f["properties"] for f in fc["features"]}
    assert set(by_ext) == {"1", "2"}
    assert by_ext["1"]["active"] is True and by_ext["1"]["status"] == "Queued"
    assert by_ext["2"]["active"] is False and by_ext["2"]["status"] == "Closed"


async def test_entities_zero_window_excludes_closed(db_session):
    await _seed(db_session)
    # A zero-minute window excludes anything closed before "now".
    fc = await entities(source="test", closed_within=0, session=db_session)
    assert {f["properties"]["external_id"] for f in fc["features"]} == {"1"}


async def test_entities_inactive_only(db_session):
    await _seed(db_session)
    fc = await entities(active=False, source="test", session=db_session)
    assert {f["properties"]["external_id"] for f in fc["features"]} == {"2"}


async def test_snapshot_has_no_track(db_session):
    await _seed(db_session)
    d = await entity_detail(await _entity_id(db_session, "1"), session=db_session)
    assert "track" not in d
    assert d["external_id"] == "1" and d["is_active"] is True


async def test_track_ordered_oldest_first(db_session):
    await ingest(db_session, "test", [_obs("1", "Queued")])
    await ingest(db_session, "test", [_obs("1", "Enroute")])
    track = await entity_track(await _entity_id(db_session, "1"), session=db_session)
    assert [t["status"] for t in track] == ["Queued", "Enroute"]
    times = [t["observed_at"] for t in track]
    assert times == sorted(times)


async def test_polygon_entity_round_trips_as_polygon(db_session):
    ring = [[-85.3, 35.0], [-85.3, 35.1], [-85.2, 35.1], [-85.2, 35.0], [-85.3, 35.0]]
    poly = NormalizedObservation(
        external_id="p1",
        category="general",
        label="Advisory",
        geometry={"type": "Polygon", "coordinates": [ring]},
        status="Planned Work",
        properties={"status": "Planned Work"},
    )
    await ingest(db_session, "test", [poly])

    fc = await entities(source="test", session=db_session)
    [feat] = fc["features"]
    assert feat["geometry"]["type"] == "Polygon"

    eid = (
        await db_session.execute(
            select(Entity.id).where(Entity.source_key == "test", Entity.external_id == "p1")
        )
    ).scalar_one()
    track = await entity_track(eid, session=db_session)
    assert track[0]["geometry"]["type"] == "Polygon"
    # point convenience scalars are null for polygon geometry
    assert track[0]["lon"] is None and track[0]["lat"] is None


async def test_unknown_entity_404s(db_session):
    with pytest.raises(HTTPException) as ei:
        await entity_detail(-1, session=db_session)
    assert ei.value.status_code == 404
    with pytest.raises(HTTPException) as ei:
        await entity_track(-1, session=db_session)
    assert ei.value.status_code == 404
