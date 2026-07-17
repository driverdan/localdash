"""Offline route-shape tests for the /api/v1 surface (no DB required).

Validation and 404s fire before any query executes, so these run without a
reachable Postgres. DB-backed behavior tests live in test_api_timeseries.py.
"""

from __future__ import annotations

import httpx
import pytest
from starlette.testclient import TestClient

from app.main import app


@pytest.fixture
async def client():
    # ASGITransport doesn't run the lifespan; provide the state refresh() reads.
    app.state.collectors = {}
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_old_flat_routes_are_gone(client):
    for path in [
        "/api/active",
        "/api/entities/1",
        "/api/observations",
        "/api/sources",
        "/api/config",
    ]:
        r = await client.get(path)
        assert r.status_code == 404, path


async def test_entities_malformed_bbox_rejected(client):
    r = await client.get("/api/v1/timeseries/entities", params={"bbox": "not-a-bbox"})
    assert r.status_code == 400
    assert "minLon,minLat,maxLon,maxLat" in r.json()["detail"]


async def test_observations_limit_capped(client):
    r = await client.get("/api/v1/timeseries/observations", params={"limit": 50001})
    assert r.status_code == 422


async def test_refresh_unknown_source_404(client):
    r = await client.post("/api/v1/timeseries/sources/nope/refresh")
    assert r.status_code == 404


def test_live_ws_is_global_not_feature_scoped():
    # TestClient outside a `with` block skips the lifespan (no DB/scheduler).
    tc = TestClient(app)
    with tc.websocket_connect("/api/v1/ws"):
        pass  # accepted: the global bus endpoint exists
    # The old feature-scoped endpoint must not accept; the exact exception is
    # an artifact of the catch-all static mount, so only non-acceptance matters.
    connected = False
    try:
        with tc.websocket_connect("/api/v1/timeseries/ws"):
            connected = True
    except Exception:  # noqa: BLE001
        pass
    assert not connected


async def test_config_returns_tile_fields(client):
    r = await client.get("/api/v1/config")
    assert r.status_code == 200
    body = r.json()
    assert "tile_url" in body and "tile_attribution" in body
