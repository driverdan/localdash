"""App-shell routes: feature-agnostic endpoints mounted directly at /api/v1.

Feature routers (e.g. app/api/timeseries.py) own their own /api/v1/<feature>/
namespaces; only cross-feature endpoints belong here.
"""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.ws import manager

router = APIRouter()


@router.get("/config")
async def config():
    """Frontend bootstrap config (map tiles, etc.)."""
    s = get_settings()
    return {"tile_url": s.tile_url, "tile_attribution": s.tile_attribution}


@router.websocket("/ws")
async def ws_live(ws: WebSocket):
    """The global live-update bus: all features' diffs and pings, one socket."""
    await manager.connect(ws)
    try:
        while True:
            # We don't expect client messages; this keeps the socket open.
            await ws.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(ws)
    except Exception:  # noqa: BLE001
        await manager.disconnect(ws)
