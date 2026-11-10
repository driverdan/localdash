"""App-shell routes: feature-agnostic endpoints mounted directly at /api/v1.

Feature routers (e.g. app/api/timeseries.py) own their own /api/v1/<feature>/
namespaces; only cross-feature endpoints belong here.
"""

from __future__ import annotations

import contextlib

from fastapi import APIRouter, Depends, WebSocket

from app.config import Settings, get_settings
from app.contracts import ApiModel
from app.ws import manager

router = APIRouter()


class AppConfig(ApiModel):
    """Frontend bootstrap config."""

    tile_url: str
    tile_attribution: str


@router.get("/config", response_model=AppConfig)
async def config(settings: Settings = Depends(get_settings)) -> AppConfig:
    """Frontend bootstrap config (map tiles, etc.)."""
    return AppConfig(tile_url=settings.tile_url, tile_attribution=settings.tile_attribution)


@router.websocket("/ws")
async def ws_live(ws: WebSocket) -> None:
    """The global live-update bus: all features' diffs and pings, one socket."""
    await manager.connect(ws)
    try:
        # A client close (WebSocketDisconnect) or a broken socket ends the session;
        # neither is an error worth surfacing.
        with contextlib.suppress(Exception):
            while True:
                # We don't expect client messages; this keeps the socket open.
                await ws.receive_text()
    finally:
        await manager.disconnect(ws)
