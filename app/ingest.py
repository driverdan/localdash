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

from datetime import datetime, timezone

from sqlalchemy import func, or_, select

from app.collectors.base import NormalizedObservation
from app.geojson import feature
from app.models import Entity, Observation
from app.schemas import Diff

# Minimum coordinate delta (~0.1 m) treated as movement.
POSITION_EPS = 1e-6


def state_changed(
    prev_status: str | None,
    prev_lat: float | None,
    prev_lon: float | None,
    prev_active: bool,
    new_status: str | None,
    new_lat: float | None,
    new_lon: float | None,
) -> bool:
    """True if a new observation should be recorded."""
    if not prev_active:
        return True  # entity reappeared after being closed
    if (prev_status or None) != (new_status or None):
        return True
    return _moved(prev_lat, new_lat) or _moved(prev_lon, new_lon)


def _moved(a: float | None, b: float | None) -> bool:
    if a is None and b is None:
        return False
    if a is None or b is None:
        return True
    return abs(a - b) > POSITION_EPS


def _ewkt(lat: float | None, lon: float | None) -> str | None:
    return f"SRID=4326;POINT({lon} {lat})" if lat is not None and lon is not None else None


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
    return feature(obs.lon, obs.lat, props, fid=entity.id)


async def ingest(session, source_key: str, observations: list[NormalizedObservation]) -> Diff:
    now = datetime.now(timezone.utc)
    diff = Diff(source_key=source_key)

    incoming_ids = [o.external_id for o in observations]

    # Load entities we might touch: all active ones (for closure) + any present now.
    rows = (
        await session.execute(
            select(
                Entity,
                func.ST_X(Entity.last_geom),
                func.ST_Y(Entity.last_geom),
            ).where(
                Entity.source_key == source_key,
                or_(Entity.is_active.is_(True), Entity.external_id.in_(incoming_ids)),
            )
        )
    ).all()
    existing: dict[str, tuple[Entity, float | None, float | None]] = {
        ent.external_id: (ent, lon, lat) for ent, lon, lat in rows
    }

    seen: set[str] = set()

    for obs in observations:
        seen.add(obs.external_id)
        prev = existing.get(obs.external_id)
        geom = _ewkt(obs.lat, obs.lon)

        if prev is None:
            entity = Entity(
                source_key=source_key,
                external_id=obs.external_id,
                category=obs.category,
                label=obs.label,
                first_seen_at=now,
                last_seen_at=now,
                is_active=True,
                last_geom=geom,
                latest_properties=obs.properties,
            )
            session.add(entity)
            await session.flush()  # assign entity.id
            session.add(_observation(entity.id, source_key, now, obs, geom))
            diff.new.append(_entity_feature(entity, obs))
            continue

        entity, prev_lon, prev_lat = prev
        changed = state_changed(
            entity.latest_properties.get("status") if entity.latest_properties else None,
            prev_lat,
            prev_lon,
            entity.is_active,
            obs.status,
            obs.lat,
            obs.lon,
        )

        entity.category = obs.category
        entity.label = obs.label
        entity.last_seen_at = now
        entity.last_geom = geom
        entity.latest_properties = obs.properties
        entity.is_active = True

        if changed:
            session.add(_observation(entity.id, source_key, now, obs, geom))
            diff.updated.append(_entity_feature(entity, obs))

    # Closure sweep — active entities absent from this payload.
    for external_id, (entity, _lon, _lat) in existing.items():
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
