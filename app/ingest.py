"""Ingestion service.

Takes the normalized observations from a collector and reconciles them against
stored state for that source:

  1. Upsert each observed entity (latest snapshot, last_seen, geom, active).
  2. Append a new observation row *only when the state changed* (status moved or
     the entity moved) — so we don't store one duplicate row per poll.
  3. Closure sweep: entities that were active but are absent from this payload
     are marked inactive with a final "Closed" observation.

Returns a Diff describing new/updated/closed entities for WebSocket broadcast.

The pure change-detection rule lives in `state_changed()` so it is unit-testable
without a database.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, or_, select

from app.collectors.base import NormalizedObservation
from app.geojson import feature, feature_geom
from app.models import Entity, Observation
from app.schemas import Diff

# Coordinate rounding (6 decimals ≈ 0.1 m) applied to geometry fingerprints, so a
# point that jitters below that threshold produces the same fingerprint and does
# not record a new observation (preserving the prior movement behavior).
_FP_DECIMALS = 6


def state_changed(
    prev_status: str | None,
    prev_fingerprint: str | None,
    prev_active: bool,
    new_status: str | None,
    new_fingerprint: str | None,
) -> bool:
    """True if a new observation should be recorded."""
    if not prev_active:
        return True  # entity reappeared after being closed
    if (prev_status or None) != (new_status or None):
        return True
    return (prev_fingerprint or None) != (new_fingerprint or None)


def _round_coords(coords: Any) -> Any:
    """Recursively round a GeoJSON coordinate structure to _FP_DECIMALS."""
    if isinstance(coords, (int, float)):
        return round(float(coords), _FP_DECIMALS)
    if isinstance(coords, (list, tuple)):
        return [_round_coords(c) for c in coords]
    return coords


def geom_fingerprint(obs: NormalizedObservation) -> str | None:
    """Stable fingerprint of an observation's geometry for change detection.

    Point form (`lon,lat` at 6 decimals) preserves the prior ~0.1 m threshold;
    polygon/other geometry hashes its coordinate-rounded GeoJSON so a reshape is
    detected while sub-0.1 m noise is not.
    """
    if obs.geometry is not None:
        canonical = {
            "type": obs.geometry.get("type"),
            "coordinates": _round_coords(obs.geometry.get("coordinates")),
        }
        blob = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
        return hashlib.sha1(blob.encode()).hexdigest()
    if obs.lat is not None and obs.lon is not None:
        return f"{obs.lon:.6f},{obs.lat:.6f}"
    return None


def _geom_value(obs: NormalizedObservation):
    """SQL/EWKT geometry value for `obs`, or None when it has no geometry.

    Explicit GeoJSON geometry (polygon sources) is built with ST_GeomFromGeoJSON;
    point sources keep the fast EWKT-string path (wrapped by GeoAlchemy2).
    """
    if obs.geometry is not None:
        return func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(obs.geometry)), 4326)
    if obs.lat is not None and obs.lon is not None:
        return f"SRID=4326;POINT({obs.lon} {obs.lat})"
    return None


def _entity_feature(entity: Entity, obs: NormalizedObservation) -> dict:
    props = {
        "id": entity.id,
        "source": entity.source_key,
        "external_id": entity.external_id,
        "category": entity.category,
        "label": entity.label,
        "status": obs.status,
        **obs.properties,
    }
    if obs.geometry is not None:
        return feature_geom(obs.geometry, props, fid=entity.id)
    return feature(obs.lon, obs.lat, props, fid=entity.id)


async def ingest(session, source_key: str, observations: list[NormalizedObservation]) -> Diff:
    now = datetime.now(timezone.utc)
    diff = Diff(source_key=source_key)

    incoming_ids = [o.external_id for o in observations]

    # Load entities we might touch: all active ones (for closure) + any present now.
    # Geometry change is detected via the stored fingerprint, so we no longer need
    # ST_X/ST_Y (which are point-only and NULL for polygons).
    existing: dict[str, Entity] = {
        ent.external_id: ent
        for ent in (
            await session.execute(
                select(Entity).where(
                    Entity.source_key == source_key,
                    or_(Entity.is_active.is_(True), Entity.external_id.in_(incoming_ids)),
                )
            )
        )
        .scalars()
        .all()
    }

    seen: set[str] = set()

    for obs in observations:
        seen.add(obs.external_id)
        entity = existing.get(obs.external_id)
        geom = _geom_value(obs)
        fingerprint = geom_fingerprint(obs)

        if entity is None:
            entity = Entity(
                source_key=source_key,
                external_id=obs.external_id,
                category=obs.category,
                label=obs.label,
                first_seen_at=now,
                last_seen_at=now,
                is_active=True,
                last_geom=geom,
                geom_fingerprint=fingerprint,
                latest_properties=obs.properties,
            )
            session.add(entity)
            await session.flush()  # assign entity.id
            session.add(_observation(entity.id, source_key, now, obs, geom))
            diff.new.append(_entity_feature(entity, obs))
            continue

        changed = state_changed(
            entity.latest_properties.get("status") if entity.latest_properties else None,
            entity.geom_fingerprint,
            entity.is_active,
            obs.status,
            fingerprint,
        )

        entity.category = obs.category
        entity.label = obs.label
        entity.last_seen_at = now
        entity.last_geom = geom
        entity.geom_fingerprint = fingerprint
        entity.latest_properties = obs.properties
        entity.is_active = True

        if changed:
            session.add(_observation(entity.id, source_key, now, obs, geom))
            diff.updated.append(_entity_feature(entity, obs))

    # Closure sweep — active entities absent from this payload.
    for external_id, entity in existing.items():
        if external_id in seen or not entity.is_active:
            continue
        entity.is_active = False
        entity.last_seen_at = now
        session.add(
            Observation(
                entity_id=entity.id,
                observed_at=now,
                source_key=source_key,
                category=entity.category,
                status="Closed",
                geom=entity.last_geom,
                properties={"reason": "absent_from_feed"},
            )
        )
        diff.closed.append(entity.id)

    await session.commit()
    return diff


def _observation(entity_id: int, source_key: str, now, obs: NormalizedObservation, geom):
    props = dict(obs.properties)
    if obs.source_time is not None:
        props.setdefault("source_time", obs.source_time.isoformat())
    return Observation(
        entity_id=entity_id,
        observed_at=now,
        source_key=source_key,
        category=obs.category,
        status=obs.status,
        geom=geom,
        properties=props,
    )
