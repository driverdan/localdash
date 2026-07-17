"""Timeseries feature: entities, observation history, sources.

Mounted at /api/v1/timeseries (see app/main.py). All geo responses are GeoJSON
FeatureCollections. Live diffs are broadcast on the global /api/v1/ws bus
(app/api/root.py), not a feature-scoped socket.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
)
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.geojson import feature_collection, feature_geom
from app.models import Entity, Observation, Source

router = APIRouter()


def _parse_geom(geom_json: str | None) -> dict | None:
    """Parse an ST_AsGeoJSON() result string into a GeoJSON geometry (or None)."""
    return json.loads(geom_json) if geom_json else None


def _bbox_filter(column, bbox: str | None):
    """Return a PostGIS bbox predicate for `column`, or None."""
    if not bbox:
        return None
    try:
        minx, miny, maxx, maxy = (float(x) for x in bbox.split(","))
    except ValueError:
        raise HTTPException(400, "bbox must be 'minLon,minLat,maxLon,maxLat'")
    return func.ST_Intersects(column, func.ST_MakeEnvelope(minx, miny, maxx, maxy, 4326))


@router.get("/entities")
async def entities(
    active: bool = True,
    source: str | None = None,
    category: str | None = None,
    bbox: str | None = None,
    closed_within: Annotated[int | None, Query(ge=0, le=10080)] = None,
    session: AsyncSession = Depends(get_session),
):
    """Tracked entities as a GeoJSON FeatureCollection.

    Defaults to active entities only — closure never deletes, so the unfiltered
    collection would be unbounded. `closed_within=N` (minutes) also includes
    entities closed within that window; `active=false` returns only inactive
    entities (within `closed_within` if given). Each feature's properties carry
    `active` so clients can style closed incidents differently.
    """
    q = select(
        Entity.id,
        Entity.source_key,
        Entity.external_id,
        Entity.category,
        Entity.label,
        Entity.last_seen_at,
        Entity.is_active,
        Entity.latest_properties,
        func.ST_AsGeoJSON(Entity.last_geom),
    )

    cutoff = (
        datetime.now(timezone.utc) - timedelta(minutes=closed_within)
        if closed_within is not None
        else None
    )
    if active:
        if cutoff is not None:
            q = q.where(or_(Entity.is_active.is_(True), Entity.last_seen_at >= cutoff))
        else:
            q = q.where(Entity.is_active.is_(True))
    else:
        q = q.where(Entity.is_active.is_(False))
        if cutoff is not None:
            q = q.where(Entity.last_seen_at >= cutoff)

    if source:
        q = q.where(Entity.source_key == source)
    if category:
        q = q.where(Entity.category == category)
    bbox_pred = _bbox_filter(Entity.last_geom, bbox)
    if bbox_pred is not None:
        q = q.where(bbox_pred)

    rows = (await session.execute(q)).all()
    feats = []
    for eid, skey, ext, cat, label, last_seen, is_active, props, geom_json in rows:
        feats.append(
            feature_geom(
                _parse_geom(geom_json),
                {
                    # raw source fields first, then our authoritative keys override them.
                    **(props or {}),
                    "id": eid,
                    "source": skey,
                    "external_id": ext,
                    "category": cat,
                    "label": label,
                    "last_seen_at": last_seen.isoformat() if last_seen else None,
                    "active": is_active,
                    "status": "Closed" if not is_active else (props or {}).get("status"),
                },
                fid=eid,
            )
        )
    return feature_collection(feats)


@router.get("/entities/{entity_id}")
async def entity_detail(entity_id: int, session: AsyncSession = Depends(get_session)):
    """Entity snapshot (no track — see /entities/{id}/track)."""
    ent = (await session.execute(select(Entity).where(Entity.id == entity_id))).scalar_one_or_none()
    if ent is None:
        raise HTTPException(404, "entity not found")

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
    }


@router.get("/entities/{entity_id}/track")
async def entity_track(entity_id: int, session: AsyncSession = Depends(get_session)):
    """The entity's full observation history, oldest first."""
    exists = (
        await session.execute(select(Entity.id).where(Entity.id == entity_id))
    ).scalar_one_or_none()
    if exists is None:
        raise HTTPException(404, "entity not found")

    obs_rows = (
        await session.execute(
            select(
                Observation.observed_at,
                Observation.status,
                Observation.properties,
                func.ST_AsGeoJSON(Observation.geom),
            )
            .where(Observation.entity_id == entity_id)
            .order_by(Observation.observed_at.asc())
        )
    ).all()

    out = []
    for at, status, props, geom_json in obs_rows:
        geometry = _parse_geom(geom_json)
        # lon/lat convenience fields stay populated only for point geometry;
        # they are null for polygons (clients read `geometry` for those).
        is_point = bool(geometry) and geometry.get("type") == "Point"
        lon, lat = geometry["coordinates"] if is_point else (None, None)
        out.append(
            {
                "observed_at": at.isoformat(),
                "status": status,
                "geometry": geometry,
                "lon": lon,
                "lat": lat,
                "properties": props,
            }
        )
    return out


@router.get("/observations")
async def observations(
    source: str | None = None,
    category: str | None = None,
    bbox: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: Annotated[int, Query(le=50000)] = 5000,
    session: AsyncSession = Depends(get_session),
):
    """Historical observations in a time window as a GeoJSON FeatureCollection."""
    q = select(
        Observation.entity_id,
        Observation.source_key,
        Observation.category,
        Observation.status,
        Observation.observed_at,
        Observation.properties,
        func.ST_AsGeoJSON(Observation.geom),
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
        feature_geom(
            _parse_geom(geom_json),
            {
                "entity_id": eid,
                "source": skey,
                "category": cat,
                "status": status,
                "observed_at": at.isoformat(),
                **(props or {}),
            },
        )
        for eid, skey, cat, status, at, props, geom_json in rows
    ]
    return feature_collection(feats)


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


@router.post("/sources/{key}/refresh")
async def refresh(key: str, request: Request):
    """Manually trigger one collection cycle (handy for testing)."""
    collectors = request.app.state.collectors
    collector = collectors.get(key)
    if collector is None:
        raise HTTPException(404, f"unknown source '{key}'")
    from app.scheduler import run_collector

    return await run_collector(collector)
