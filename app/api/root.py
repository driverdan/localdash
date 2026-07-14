"""App-shell routes: feature-agnostic endpoints mounted directly at /api/v1.

Feature routers (e.g. app/api/timeseries.py) own their own /api/v1/<feature>/
namespaces; only cross-feature endpoints belong here.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings

router = APIRouter()


@router.get("/config")
async def config():
    """Frontend bootstrap config (map tiles, etc.)."""
    s = get_settings()
    return {"tile_url": s.tile_url, "tile_attribution": s.tile_attribution}
