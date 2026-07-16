"""Events ingest: merge raw events into canonical, tagged, geocoded records.

Async port of the chattevents ingest manager. Relationships are loaded
eagerly (selectinload) — lazy loading does not work under async sessions.

Identity is resolved in tiers (see app.events.dedup): the source listing
itself, then the exact canonical key, then the location-gated fuzzy match.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.events import CHATTANOOGA_CENTER
from app.events.dedup import MatchSide, canonical_key, events_match
from app.events.dedup import haversine_miles as _haversine_miles
from app.events.geocoding import Coords, Geocoder, NullGeocoder
from app.events.models import Event, EventLink, GeocodeCache, Tag
from app.events.sources.base import EventSource, RawEvent
from app.events.tagging import tag_event

log = logging.getLogger("localdash.events")

# Candidate window for the fuzzy tier, matching dedup's start-delta gate.
_FUZZY_WINDOW = timedelta(hours=2)

_EVENT_OPTIONS = (selectinload(Event.links), selectinload(Event.tags))


def _point(coords: Coords) -> str:
    """WKT for a PostGIS point from (lat, lon)."""
    return f"SRID=4326;POINT({coords[1]} {coords[0]})"


async def _get_or_create_tag(session: AsyncSession, name: str, cache: dict[str, Tag]) -> Tag:
    if name in cache:
        return cache[name]
    tag = await session.scalar(select(Tag).where(Tag.name == name))
    if tag is None:
        # Race-safe against a concurrent ingest inserting the same name: the
        # no-op insert never violates the unique constraint, and the re-select
        # returns whichever row won.
        await session.execute(pg_insert(Tag).values(name=name).on_conflict_do_nothing())
        tag = await session.scalar(select(Tag).where(Tag.name == name))
    cache[name] = tag
    return tag


def _supplied_coords(raw: RawEvent) -> Coords | None:
    if raw.latitude is not None and raw.longitude is not None:
        return (raw.latitude, raw.longitude)
    return None


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


def _as_utc(t: datetime) -> datetime:
    if t.tzinfo is None:
        return t.replace(tzinfo=timezone.utc)
    return t.astimezone(timezone.utc)


async def _find_by_source_listing(session: AsyncSession, raw: RawEvent) -> Event | None:
    """Tier 1: the event already linking this exact source listing.

    Matched by source event id when the source provides one, else by URL,
    and gated on the same UTC start day — recurring feeds may reuse one
    id/URL across occurrences, which must stay separate events.
    """
    if raw.source_event_id:
        listing = EventLink.source_event_id == raw.source_event_id
    else:
        listing = EventLink.source_url == raw.source_url
    events = await session.scalars(
        select(Event)
        .join(EventLink)
        .where(EventLink.source_name == raw.source_name, listing)
        .options(*_EVENT_OPTIONS)
    )
    day = _as_utc(raw.start_time).date()
    return next((e for e in events if _as_utc(e.starts_at).date() == day), None)


async def _find_fuzzy_candidate(
    session: AsyncSession, raw: RawEvent, coords: Coords | None
) -> Event | None:
    """Tier 3: a stored event within the start window that events_match accepts."""
    start = _as_utc(raw.start_time)
    rows = await session.execute(
        select(Event, func.ST_Y(Event.location), func.ST_X(Event.location))
        .where(Event.starts_at.between(start - _FUZZY_WINDOW, start + _FUZZY_WINDOW))
        .options(*_EVENT_OPTIONS)
        .order_by(Event.id)
    )
    raw_side = MatchSide(
        title=raw.title,
        start=raw.start_time,
        coords=coords,
        venue_name=raw.venue_name,
        address=raw.address,
    )
    for event, lat, lon in rows:
        event_side = MatchSide(
            title=event.title,
            start=event.starts_at,
            coords=(lat, lon) if lat is not None else None,
            venue_name=event.venue_name,
            address=event.address,
        )
        if events_match(raw_side, event_side):
            return event
    return None


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
        event = await _find_by_source_listing(session, raw)
        if event is not None and event.canonical_key != key:
            # Same listing, drifted key (upstream retitle or a normalization
            # change): adopt the current key so exact lookups keep working.
            taken = await session.scalar(select(Event.id).where(Event.canonical_key == key))
            if taken is None:
                event.canonical_key = key
        if event is None:
            event = await session.scalar(
                select(Event).where(Event.canonical_key == key).options(*_EVENT_OPTIONS)
            )

        coords: Coords | None = None
        if event is None:
            # Prefer source-supplied coordinates; geocode only when absent.
            coords = _supplied_coords(raw)
            if coords is None:
                coords = await _geocode(session, geocoder, raw.address, geo_cache)
            event = await _find_fuzzy_candidate(session, raw, coords)

        if event is None:
            if max_miles > 0 and coords is not None:
                distance = _haversine_miles(CHATTANOOGA_CENTER, coords)
                if distance > max_miles:
                    skipped_far += 1
                    log.debug(
                        "skipping far event %r (%.0f mi > %.0f mi)",
                        raw.title,
                        distance,
                        max_miles,
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
            # Source-supplied tags (lowercased to merge with the keyword
            # vocabulary) replace keyword tagging entirely.
            if raw.tags:
                names = set(name.lower() for name in raw.tags)
            else:
                names = tag_event(raw.title, raw.description or "")
            for name in sorted(names):
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
            if event.ends_at is None and raw.end_time:
                event.ends_at = raw.end_time
            if event.location is None:
                coords = _supplied_coords(raw)
                if coords is None:
                    coords = await _geocode(
                        session, geocoder, event.address or raw.address, geo_cache
                    )
                if coords:
                    event.location = _point(coords)

        # One link per listing (source name + URL); a re-report of the same
        # listing refreshes its source event id rather than adding a link.
        existing = next(
            (
                link
                for link in event.links
                if link.source_name == raw.source_name and link.source_url == raw.source_url
            ),
            None,
        )
        if existing is None:
            event.links.append(
                EventLink(
                    source_name=raw.source_name,
                    source_url=raw.source_url,
                    source_event_id=raw.source_event_id,
                )
            )
        elif raw.source_event_id:
            existing.source_event_id = raw.source_event_id
        await session.flush()

    await session.commit()
    return {"created": created, "merged": merged, "skipped_far": skipped_far}


def _merge_pair(survivor: Event, loser: Event) -> None:
    """Fold loser into survivor: longer title, union links/tags, backfill."""
    if len(loser.title) > len(survivor.title):
        survivor.title = loser.title
    if not survivor.description and loser.description:
        survivor.description = loser.description
    if survivor.venue_name is None and loser.venue_name:
        survivor.venue_name = loser.venue_name
    if survivor.address is None and loser.address:
        survivor.address = loser.address
    if survivor.ends_at is None and loser.ends_at:
        survivor.ends_at = loser.ends_at
    if survivor.location is None and loser.location is not None:
        survivor.location = loser.location
    kept = {(link.source_name, link.source_url) for link in survivor.links}
    for link in list(loser.links):
        if (link.source_name, link.source_url) not in kept:
            loser.links.remove(link)
            survivor.links.append(link)
    for tag in loser.tags:
        if tag not in survivor.tags:
            survivor.tags.append(tag)


async def reconcile_events(session: AsyncSession) -> int:
    """Merge stored upcoming events the de-duplication tiers identify as one.

    Two stored rows are one event when their canonical keys — recomputed from
    the current normalization, since stored keys predating a normalization
    change go stale — are equal (exactly what would have merged them at
    ingest), or when the fuzzy matcher accepts the pair. Heals duplicates
    that predate the matcher and pairs that only became mergeable later
    (e.g. a geocode retry resolved the location gate's coordinates). Within
    each UTC-day bucket events are compared pairwise; the earlier-created row
    survives. Idempotent; returns the merge count.
    """
    rows = (
        await session.execute(
            select(Event, func.ST_Y(Event.location), func.ST_X(Event.location))
            .where(Event.starts_at >= datetime.now(timezone.utc))
            .options(*_EVENT_OPTIONS)
            .order_by(Event.id)
        )
    ).all()

    buckets: dict[dt.date, list[list]] = defaultdict(list)
    for event, lat, lon in rows:
        coords = (lat, lon) if lat is not None else None
        key = canonical_key(event.title, event.starts_at)
        buckets[_as_utc(event.starts_at).date()].append([event, coords, key])

    merged = 0
    for bucket in buckets.values():
        for i, (survivor, s_coords, s_key) in enumerate(bucket):
            if survivor is None:
                continue
            for j in range(i + 1, len(bucket)):
                loser, l_coords, l_key = bucket[j]
                if loser is None:
                    continue
                a = MatchSide(
                    title=survivor.title,
                    start=survivor.starts_at,
                    coords=s_coords,
                    venue_name=survivor.venue_name,
                    address=survivor.address,
                )
                b = MatchSide(
                    title=loser.title,
                    start=loser.starts_at,
                    coords=l_coords,
                    venue_name=loser.venue_name,
                    address=loser.address,
                )
                if s_key != l_key and not events_match(a, b):
                    continue
                log.info("reconciling duplicate events %r <- %r", survivor.title, loser.title)
                _merge_pair(survivor, loser)
                if s_coords is None and l_coords is not None:
                    s_coords = l_coords
                    bucket[i][1] = l_coords
                s_key = canonical_key(survivor.title, survivor.starts_at)
                bucket[i][2] = s_key
                await session.delete(loser)
                bucket[j][0] = None
                merged += 1

    await session.commit()
    return merged


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
