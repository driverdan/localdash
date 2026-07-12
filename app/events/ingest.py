"""Events ingest: merge raw events into canonical, tagged, geocoded records.

Async port of the chattevents ingest manager. Relationships are loaded
eagerly (selectinload) — lazy loading does not work under async sessions.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.events import CHATTANOOGA_CENTER
from app.events.dedup import canonical_key
from app.events.geocoding import Coords, Geocoder, NullGeocoder
from app.events.models import Event, EventLink, GeocodeCache, Tag
from app.events.sources.base import EventSource, RawEvent
from app.events.tagging import tag_event

log = logging.getLogger("localdash.events")


def _haversine_miles(a: Coords, b: Coords) -> float:
    """Great-circle distance in miles between two (lat, lon) points."""
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * 3958.8 * math.asin(math.sqrt(h))


def _point(coords: Coords) -> str:
    """WKT for a PostGIS point from (lat, lon)."""
    return f"SRID=4326;POINT({coords[1]} {coords[0]})"


async def _get_or_create_tag(session: AsyncSession, name: str, cache: dict[str, Tag]) -> Tag:
    if name in cache:
        return cache[name]
    tag = await session.scalar(select(Tag).where(Tag.name == name))
    if tag is None:
        tag = Tag(name=name)
        session.add(tag)
    cache[name] = tag
    return tag


async def _geocode(
    session: AsyncSession,
    geocoder: Geocoder,
    address: str | None,
    cache: dict[str, Coords | None],
) -> Coords | None:
    """Resolve an address to coordinates, using both an in-run and DB-backed cache."""
    if not address:
        return None
    if address in cache:
        return cache[address]

    row = await session.scalar(select(GeocodeCache).where(GeocodeCache.address == address))
    if row is not None:
        coords = (row.latitude, row.longitude) if row.latitude is not None else None
    else:
        coords = await geocoder.geocode(address)
        session.add(
            GeocodeCache(
                address=address,
                latitude=coords[0] if coords else None,
                longitude=coords[1] if coords else None,
                last_attempted_at=datetime.now(timezone.utc),
            )
        )
    cache[address] = coords
    return coords


async def upsert_raw_events(
    session: AsyncSession,
    raws: list[RawEvent],
    geocoder: Geocoder | None = None,
    max_miles: float = 0,
) -> dict[str, int]:
    """Insert or merge a batch of raw events.

    New events are geocoded from their address; when max_miles is positive, a
    new event geocoding farther than that from the Chattanooga center is
    dropped (merges are exempt). Returns counts of newly created vs. merged
    (duplicate) events, plus how many were skipped as too far.
    """
    geocoder = geocoder or NullGeocoder()
    created = 0
    merged = 0
    skipped_far = 0
    tag_cache: dict[str, Tag] = {}
    geo_cache: dict[str, Coords | None] = {}

    for raw in raws:
        key = canonical_key(raw.title, raw.start_time)
        event = await session.scalar(
            select(Event)
            .where(Event.canonical_key == key)
            .options(selectinload(Event.links), selectinload(Event.tags))
        )

        if event is None:
            coords = await _geocode(session, geocoder, raw.address, geo_cache)
            if max_miles > 0 and coords is not None:
                distance = _haversine_miles(CHATTANOOGA_CENTER, coords)
                if distance > max_miles:
                    skipped_far += 1
                    log.debug(
                        "skipping far event %r (%.0f mi > %.0f mi)",
                        raw.title, distance, max_miles,
                    )
                    continue
            event = Event(
                canonical_key=key,
                title=raw.title,
                description=raw.description or "",
                starts_at=raw.start_time,
                ends_at=raw.end_time,
                venue_name=raw.venue_name,
                address=raw.address,
                location=_point(coords) if coords else None,
                tags=[],
                links=[],
            )
            session.add(event)
            created += 1
            for name in sorted(tag_event(raw.title, raw.description or "")):
                event.tags.append(await _get_or_create_tag(session, name, tag_cache))
        else:
            merged += 1
            # Backfill any fields the canonical record is missing.
            if not event.description and raw.description:
                event.description = raw.description
            if event.venue_name is None and raw.venue_name:
                event.venue_name = raw.venue_name
            if event.address is None and raw.address:
                event.address = raw.address
            if event.location is None:
                coords = await _geocode(session, geocoder, event.address or raw.address, geo_cache)
                if coords:
                    event.location = _point(coords)

        # One link per source name; refresh the URL if the source already linked.
        existing = next((l for l in event.links if l.source_name == raw.source_name), None)
        if existing is None:
            event.links.append(
                EventLink(
                    source_name=raw.source_name,
                    source_url=raw.source_url,
                    source_event_id=raw.source_event_id,
                )
            )
        else:
            existing.source_url = raw.source_url
        await session.flush()

    await session.commit()
    return {"created": created, "merged": merged, "skipped_far": skipped_far}


async def retry_failed_geocodes(
    session: AsyncSession,
    geocoder: Geocoder,
    retry_hours: float,
    batch: int,
) -> dict[str, int]:
    """Re-attempt cached geocode failures whose last attempt is stale.

    Takes up to ``batch`` coordinate-less cache rows last attempted more than
    ``retry_hours`` ago, oldest first. A success stores the coordinates and
    backfills the location of every stored event with that address; a failure
    just bumps last_attempted_at so the row waits out another age window.
    A non-positive ``retry_hours`` disables the pass.
    """
    if retry_hours <= 0 or batch <= 0:
        return {"retried": 0, "resolved": 0}

    cutoff = datetime.now(timezone.utc) - timedelta(hours=retry_hours)
    rows = (
        await session.scalars(
            select(GeocodeCache)
            .where(GeocodeCache.latitude.is_(None), GeocodeCache.last_attempted_at < cutoff)
            .order_by(GeocodeCache.last_attempted_at)
            .limit(batch)
        )
    ).all()

    resolved = 0
    for row in rows:
        coords = await geocoder.geocode(row.address)
        row.last_attempted_at = datetime.now(timezone.utc)
        if coords is not None:
            row.latitude, row.longitude = coords
            resolved += 1
            await session.execute(
                update(Event)
                .where(Event.address == row.address, Event.location.is_(None))
                .values(location=_point(coords))
            )
    await session.commit()
    return {"retried": len(rows), "resolved": resolved}


async def run_sources(
    session: AsyncSession,
    sources: list[EventSource],
    geocoder: Geocoder | None = None,
    max_miles: float = 0,
) -> dict[str, int]:
    """Fetch every source and persist the combined result.

    A failure in one source does not abort the others.
    """
    raws: list[RawEvent] = []
    for source in sources:
        try:
            raws.extend(await source.fetch())
        except Exception:  # noqa: BLE001 — defensive against flaky feeds
            log.exception("event source %s failed", getattr(source, "name", source))
    return await upsert_raw_events(session, raws, geocoder, max_miles=max_miles)
