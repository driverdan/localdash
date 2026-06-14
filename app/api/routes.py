"""REST + WebSocket endpoints. All geo responses are GeoJSON FeatureCollections."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.geojson import feature, feature_collection
from app.models import Entity, Observation, Source
from app.ws import manager

router = APIRouter()


@router.get("/config")
async def config():
    """Frontend bootstrap config (map tiles, etc.)."""
    s = get_settings()
    return {"tile_url": s.tile_url, "tile_attribution": s.tile_attribution}


@router.get("/sources")
async def list_sources(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(Source))).scalars().all()
    return [
        {
            "key": r.key,
            "name": r.name,
            "enabled": r.enabled,
            "poll_interval_seconds": r.poll_interval_seconds,
            "last_run_at": r.last_run_at.isoformat() if r.last_run_at else None,
            "last_status": r.last_status,
            "last_error": r.last_error,
            "last_count": r.last_count,
        }
        for r in rows
    ]


def _bbox_filter(column, bbox: str | None):
    """Return a PostGIS bbox predicate for `column`, or None."""
    if not bbox:
        return None
    try:
        minx, miny, maxx, maxy = (float(x) for x in bbox.split(","))
    except ValueError:
        raise HTTPException(400, "bbox must be 'minLon,minLat,maxLon,maxLat'")
    return func.ST_Intersects(column, func.ST_MakeEnvelope(minx, miny, maxx, maxy, 4326))


@router.get("/active")
async def active(
    source: str | None = None,
    category: str | None = None,
    bbox: str | None = None,
    include_closed: bool = False,
    closed_within_minutes: int = Query(60, ge=0, le=10080),
    session: AsyncSession = Depends(get_session),
):
    """Active entities as a GeoJSON FeatureCollection.

    With `include_closed=true`, recently-closed entities (inactive, last seen
    within `closed_within_minutes`) are included too. Each feature's properties
    carry `active` so clients can style closed incidents differently.
    """
    q = select(
        Entity.id, Entity.source_key, Entity.external_id, Entity.category,
        Entity.label, Entity.last_seen_at, Entity.is_active, Entity.latest_properties,
        func.ST_X(Entity.last_geom), func.ST_Y(Entity.last_geom),
    )

    if include_closed:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=closed_within_minutes)
        q = q.where(or_(Entity.is_active.is_(True), Entity.last_seen_at >= cutoff))
    else:
        q = q.where(Entity.is_active.is_(True))

    if source:
        q = q.where(Entity.source_key == source)
    if category:
        q = q.where(Entity.category == category)
    bbox_pred = _bbox_filter(Entity.last_geom, bbox)
    if bbox_pred is not None:
        q = q.where(bbox_pred)

    rows = (await session.execute(q)).all()
    feats = []
    for eid, skey, ext, cat, label, last_seen, is_active, props, lon, lat in rows:
        feats.append(
            feature(
                lon, lat,
                {
                    # raw source fields first, then our authoritative keys override them.
                    **(props or {}),
                    "id": eid, "source": skey, "external_id": ext, "category": cat,
                    "label": label, "last_seen_at": last_seen.isoformat() if last_seen else None,
                    "active": is_active,
                    "status": "Closed" if not is_active else (props or {}).get("status"),
                },
                fid=eid,
            )
        )
    return feature_collection(feats)


@router.get("/entities/{entity_id}")
async def entity_detail(entity_id: int, session: AsyncSession = Depends(get_session)):
    """Entity snapshot + its full observation track (history)."""
    ent = (
        await session.execute(select(Entity).where(Entity.id == entity_id))
    ).scalar_one_or_none()
    if ent is None:
        raise HTTPException(404, "entity not found")

    obs_rows = (
        await session.execute(
            select(
                Observation.observed_at, Observation.status, Observation.properties,
                func.ST_X(Observation.geom), func.ST_Y(Observation.geom),
            )
            .where(Observation.entity_id == entity_id)
            .order_by(Observation.observed_at.asc())
        )
    ).all()

    track = [
        {
            "observed_at": at.isoformat(),
            "status": status,
            "lon": lon, "lat": lat,
            "properties": props,
        }
        for at, status, props, lon, lat in obs_rows
    ]
    return {
        "id": ent.id,
        "source": ent.source_key,
        "external_id": ent.external_id,
        "category": ent.category,
        "label": ent.label,
        "is_active": ent.is_active,
        "first_seen_at": ent.first_seen_at.isoformat() if ent.first_seen_at else None,
        "last_seen_at": ent.last_seen_at.isoformat() if ent.last_seen_at else None,
        "latest_properties": ent.latest_properties,
        "track": track,
    }


@router.get("/observations")
async def observations(
    source: str | None = None,
    category: str | None = None,
    bbox: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(5000, le=50000),
    session: AsyncSession = Depends(get_session),
):
    """Historical observations in a time window as a GeoJSON FeatureCollection."""
    q = select(
        Observation.entity_id, Observation.source_key, Observation.category,
        Observation.status, Observation.observed_at, Observation.properties,
        func.ST_X(Observation.geom), func.ST_Y(Observation.geom),
    )
    if source:
        q = q.where(Observation.source_key == source)
    if category:
        q = q.where(Observation.category == category)
    if start:
        q = q.where(Observation.observed_at >= start)
    if end:
        q = q.where(Observation.observed_at <= end)
    bbox_pred = _bbox_filter(Observation.geom, bbox)
    if bbox_pred is not None:
        q = q.where(bbox_pred)
    q = q.order_by(Observation.observed_at.desc()).limit(limit)

    rows = (await session.execute(q)).all()
    feats = [
        feature(
            lon, lat,
            {
                "entity_id": eid, "source": skey, "category": cat, "status": status,
                "observed_at": at.isoformat(), **(props or {}),
            },
        )
        for eid, skey, cat, status, at, props, lon, lat in rows
    ]
    return feature_collection(feats)


@router.post("/sources/{key}/refresh")
async def refresh(key: str, request: Request):
    """Manually trigger one collection cycle (handy for testing)."""
    collectors = request.app.state.collectors
    collector = collectors.get(key)
    if collector is None:
        raise HTTPException(404, f"unknown source '{key}'")
    from app.scheduler import run_collector

    return await run_collector(collector)


@router.websocket("/ws/live")
async def ws_live(ws: WebSocket, source: str | None = Query(None)):
    await manager.connect(ws, source)
    try:
        while True:
            # We don't expect client messages; this keeps the socket open.
            await ws.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(ws)
    except Exception:  # noqa: BLE001
        await manager.disconnect(ws)
