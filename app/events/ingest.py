"""Events ingest: merge raw events into canonical, tagged, geocoded records.

Async port of the chattevents ingest manager. Relationships are loaded
eagerly (selectinload) — lazy loading does not work under async sessions.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.events.dedup import canonical_key
from app.events.geocoding import Coords, Geocoder, NullGeocoder
from app.events.models import Event, EventLink, GeocodeCache, Tag
from app.events.sources.base import EventSource, RawEvent
from app.events.tagging import tag_event

log = logging.getLogger("localdash.events")


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
            )
        )
    cache[address] = coords
    return coords


async def upsert_raw_events(
    session: AsyncSession,
    raws: list[RawEvent],
    geocoder: Geocoder | None = None,
) -> dict[str, int]:
    """Insert or merge a batch of raw events.

    New events are geocoded from their address. Returns counts of newly created
    vs. merged (duplicate) events.
    """
    geocoder = geocoder or NullGeocoder()
    created = 0
    merged = 0
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
    return {"created": created, "merged": merged}


async def run_sources(
    session: AsyncSession,
    sources: list[EventSource],
    geocoder: Geocoder | None = None,
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
    return await upsert_raw_events(session, raws, geocoder)
