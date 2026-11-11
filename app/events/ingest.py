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
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.events.dedup import MatchSide, canonical_key, events_match
from app.events.dedup import haversine_miles as _haversine_miles
from app.events.geocoding import Coords, Geocoder, NullGeocoder
from app.events.models import Event, EventLink, GeocodeCache, Tag
from app.events.sources.base import EventSource, RawEvent
from app.events.tagging import tag_event
from app.geo import ewkt_point
from app.timeutil import as_utc

log = logging.getLogger("localdash.events")

# Candidate window for the fuzzy tier, matching dedup's start-delta gate.
_FUZZY_WINDOW = timedelta(hours=2)

_EVENT_OPTIONS = (selectinload(Event.links), selectinload(Event.tags))


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


async def purge_blocked_tags(session: AsyncSession, blocked: Collection[str]) -> int:
    """Delete every tag named in ``blocked``; the event_tags cascade detaches
    them from all events. No-op when the blocklist is empty. Returns the rows
    deleted."""
    if not blocked:
        return 0
    result = await session.execute(delete(Tag).where(Tag.name.in_(blocked)))
    await session.commit()
    return result.rowcount or 0


def _supplied_coords(raw: RawEvent) -> Coords | None:
    if raw.latitude is not None and raw.longitude is not None:
        return (raw.latitude, raw.longitude)
    return None


def _coords(lat: float | None, lon: float | None) -> Coords | None:
    """A (lat, lon) tuple from nullable columns; None when the latitude is missing."""
    return (lat, lon) if lat is not None else None


async def _geocode(
    session: AsyncSession,
    geocoder: Geocoder,
    address: str | None,
    cache: dict[str, Coords | None],
    now: datetime,
) -> Coords | None:
    """Resolve an address to coordinates, using both an in-run and DB-backed cache.

    A new cache row is stamped ``last_attempted_at=now``.
    """
    if not address:
        return None
    if address in cache:
        return cache[address]

    row = await session.scalar(select(GeocodeCache).where(GeocodeCache.address == address))
    if row is not None:
        coords = _coords(row.latitude, row.longitude)
    else:
        coords = await geocoder.geocode(address)
        session.add(
            GeocodeCache(
                address=address,
                latitude=coords[0] if coords else None,
                longitude=coords[1] if coords else None,
                last_attempted_at=now,
            )
        )
    cache[address] = coords
    return coords


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
    day = as_utc(raw.start_time).date()
    return next((e for e in events if as_utc(e.starts_at).date() == day), None)


async def _find_known_event(session: AsyncSession, raw: RawEvent, key: str) -> Event | None:
    """Tiers 1-2: the source listing (adopting a drifted key), then the exact canonical key."""
    event = await _find_by_source_listing(session, raw)
    if event is not None:
        if event.canonical_key != key:
            # Same listing, drifted key (upstream retitle or a normalization
            # change): adopt the current key so exact lookups keep working.
            taken = await session.scalar(select(Event.id).where(Event.canonical_key == key))
            if taken is None:
                event.canonical_key = key
        return event
    return await session.scalar(
        select(Event).where(Event.canonical_key == key).options(*_EVENT_OPTIONS)
    )


def _event_side(event: Event, coords: Coords | None) -> MatchSide:
    """A stored event's matching signals, with its coordinates read separately."""
    return MatchSide(
        title=event.title,
        start=event.starts_at,
        coords=coords,
        venue_name=event.venue_name,
        address=event.address,
    )


async def _find_fuzzy_candidate(
    session: AsyncSession, raw: RawEvent, coords: Coords | None
) -> Event | None:
    """Tier 3: a stored event within the start window that events_match accepts."""
    start = as_utc(raw.start_time)
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
        if events_match(raw_side, _event_side(event, _coords(lat, lon))):
            return event
    return None


async def _locate(
    session: AsyncSession,
    geocoder: Geocoder,
    raw: RawEvent,
    address: str | None,
    geo_cache: dict[str, Coords | None],
    now: datetime,
) -> Coords | None:
    """Source-supplied coordinates when present, else geocode ``address`` (stamped ``now``)."""
    coords = _supplied_coords(raw)
    if coords is None:
        coords = await _geocode(session, geocoder, address, geo_cache, now)
    return coords


def _beyond_radius(raw: RawEvent, coords: Coords | None, max_miles: float, center: Coords) -> bool:
    """Ingest radius filter: True when a located new event lies beyond max_miles of center."""
    if max_miles <= 0 or coords is None:
        return False
    distance = _haversine_miles(center, coords)
    if distance <= max_miles:
        return False
    log.debug(
        "skipping far event %r (%.0f mi > %.0f mi)",
        raw.title,
        distance,
        max_miles,
    )
    return True


def _tag_names(raw: RawEvent, blocked_tags: Collection[str]) -> set[str]:
    """Tag names for a new event: supplied tags, else keyword tags, minus the blocklist."""
    # Source-supplied tags (lowercased to merge with the keyword
    # vocabulary) replace keyword tagging entirely.
    if raw.tags:
        names = set(name.lower() for name in raw.tags)
    else:
        names = tag_event(raw.title, raw.description or "")
    # Blocklisted topics are never created or attached (both paths).
    return names.difference(blocked_tags)


async def _create_event(
    session: AsyncSession,
    raw: RawEvent,
    key: str,
    coords: Coords | None,
    blocked_tags: Collection[str],
    tag_cache: dict[str, Tag],
) -> Event:
    """Add a new canonical event for raw, then attach its tags in sorted order."""
    event = Event(
        canonical_key=key,
        title=raw.title,
        description=raw.description or "",
        starts_at=raw.start_time,
        ends_at=raw.end_time,
        venue_name=raw.venue_name,
        address=raw.address,
        image_url=raw.image_url,
        location=ewkt_point(*coords) if coords else None,
        tags=[],
        links=[],
    )
    # Added before any tag lookup: _get_or_create_tag's SELECTs autoflush.
    session.add(event)
    for name in sorted(_tag_names(raw, blocked_tags)):
        event.tags.append(await _get_or_create_tag(session, name, tag_cache))
    return event


def _backfill_missing(
    event: Event,
    *,
    description: str | None,
    venue_name: str | None,
    address: str | None,
    ends_at: datetime | None,
    image_url: str | None,
) -> None:
    """The shared merge backfill rule: fill empty fields, never overwrite a stored value."""
    if not event.description and description:
        event.description = description
    if event.venue_name is None and venue_name:
        event.venue_name = venue_name
    if event.address is None and address:
        event.address = address
    if event.ends_at is None and ends_at:
        event.ends_at = ends_at
    if event.image_url is None and image_url:
        event.image_url = image_url


async def _merge_report(
    session: AsyncSession,
    event: Event,
    raw: RawEvent,
    geocoder: Geocoder,
    geo_cache: dict[str, Coords | None],
    now: datetime,
) -> None:
    """Merge a matched report into its event: backfill, then locate if still unlocated."""
    _backfill_missing(
        event,
        description=raw.description,
        venue_name=raw.venue_name,
        address=raw.address,
        ends_at=raw.end_time,
        image_url=raw.image_url,
    )
    if event.location is None:
        # Read after the backfill: the report may have just supplied the address.
        coords = await _locate(session, geocoder, raw, event.address or raw.address, geo_cache, now)
        if coords:
            event.location = ewkt_point(*coords)


def _upsert_link(event: Event, raw: RawEvent) -> None:
    """One link per listing (source name + URL); a re-report refreshes its source event id."""
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


async def upsert_raw_events(
    session: AsyncSession,
    raws: list[RawEvent],
    geocoder: Geocoder | None = None,
    max_miles: float = 0,
    *,
    blocked_tags: Collection[str] = frozenset(),
    center: Coords | None = None,
    now: datetime | None = None,
) -> dict[str, int]:
    """Insert or merge a batch of raw events.

    New events are geocoded from their address; when max_miles is positive, a
    new event geocoding farther than that from ``center`` is dropped (merges
    are exempt), and ``center`` is required (ValueError without it). Tags named
    in ``blocked_tags`` are never attached to a new event. New geocode-cache
    rows are stamped with ``now`` (default: the current UTC time, read once).
    Returns counts of newly created vs. merged (duplicate) events, plus how
    many were skipped as too far.
    """
    if max_miles > 0 and center is None:
        raise ValueError("upsert_raw_events: max_miles > 0 requires a center")
    if now is None:
        now = datetime.now(timezone.utc)
    geocoder = geocoder or NullGeocoder()
    created = 0
    merged = 0
    skipped_far = 0
    tag_cache: dict[str, Tag] = {}
    geo_cache: dict[str, Coords | None] = {}

    for raw in raws:
        key = canonical_key(raw.title, raw.start_time)
        event = await _find_known_event(session, raw, key)
        coords: Coords | None = None
        if event is None:
            # Tier 3 needs coordinates; locate only once tiers 1-2 miss.
            coords = await _locate(session, geocoder, raw, raw.address, geo_cache, now)
            event = await _find_fuzzy_candidate(session, raw, coords)
        if event is None:
            if center is not None and _beyond_radius(raw, coords, max_miles, center):
                skipped_far += 1
                continue
            event = await _create_event(session, raw, key, coords, blocked_tags, tag_cache)
            created += 1
        else:
            await _merge_report(session, event, raw, geocoder, geo_cache, now)
            merged += 1
        _upsert_link(event, raw)
        await session.flush()

    await session.commit()
    return {"created": created, "merged": merged, "skipped_far": skipped_far}


def _merge_pair(survivor: Event, loser: Event) -> None:
    """Fold loser into survivor: longer title, union links/tags, backfill."""
    if len(loser.title) > len(survivor.title):
        survivor.title = loser.title
    _backfill_missing(
        survivor,
        description=loser.description,
        venue_name=loser.venue_name,
        address=loser.address,
        ends_at=loser.ends_at,
        image_url=loser.image_url,
    )
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


@dataclass
class _Candidate:
    """A stored upcoming event under reconciliation, with its evolving match state."""

    event: Event
    coords: Coords | None
    key: str  # canonical_key recomputed under the current normalization


async def _reconcile_bucket(session: AsyncSession, candidates: list[_Candidate]) -> int:
    """Merge one UTC-day bucket in id order; each survivor absorbs every later match.

    The earliest remaining row survives and is compared with every later
    row, its title, coordinates and key updated as it absorbs them. Rows it
    does not absorb, in their original order, are the next round's
    candidates. Returns the merge count.
    """
    merged = 0
    remaining = candidates
    while remaining:
        survivor, *rest = remaining
        remaining = []
        for other in rest:
            if survivor.key != other.key and not events_match(
                _event_side(survivor.event, survivor.coords),
                _event_side(other.event, other.coords),
            ):
                remaining.append(other)
                continue
            log.info(
                "reconciling duplicate events %r <- %r", survivor.event.title, other.event.title
            )
            _merge_pair(survivor.event, other.event)
            if survivor.coords is None and other.coords is not None:
                survivor.coords = other.coords
            survivor.key = canonical_key(survivor.event.title, survivor.event.starts_at)
            await session.delete(other.event)
            merged += 1
    return merged


async def reconcile_events(session: AsyncSession, *, now: datetime | None = None) -> int:
    """Merge stored upcoming events the de-duplication tiers identify as one.

    Two stored rows are one event when their canonical keys — recomputed from
    the current normalization, since stored keys predating a normalization
    change go stale — are equal (exactly what would have merged them at
    ingest), or when the fuzzy matcher accepts the pair. Heals duplicates
    that predate the matcher and pairs that only became mergeable later
    (e.g. a geocode retry resolved the location gate's coordinates). Within
    each UTC-day bucket events are compared pairwise; the earlier-created row
    survives. Only events starting at or after ``now`` (default: the current
    UTC time) are considered. Idempotent; returns the merge count.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    rows = (
        await session.execute(
            select(Event, func.ST_Y(Event.location), func.ST_X(Event.location))
            .where(Event.starts_at >= now)
            .options(*_EVENT_OPTIONS)
            .order_by(Event.id)
        )
    ).all()

    buckets: dict[dt.date, list[_Candidate]] = defaultdict(list)
    for event, lat, lon in rows:
        candidate = _Candidate(
            event, _coords(lat, lon), canonical_key(event.title, event.starts_at)
        )
        buckets[as_utc(event.starts_at).date()].append(candidate)

    merged = 0
    for bucket in buckets.values():
        merged += await _reconcile_bucket(session, bucket)

    await session.commit()
    return merged


async def retry_failed_geocodes(
    session: AsyncSession,
    geocoder: Geocoder,
    retry_hours: float,
    batch: int,
    *,
    now: datetime | None = None,
) -> dict[str, int]:
    """Re-attempt cached geocode failures whose last attempt is stale.

    Takes up to ``batch`` coordinate-less cache rows last attempted more than
    ``retry_hours`` ago, oldest first. A success stores the coordinates and
    backfills the location of every stored event with that address; a failure
    just bumps last_attempted_at so the row waits out another age window.
    A non-positive ``retry_hours`` disables the pass. Age is measured from
    ``now`` (default: the current UTC time, read once), and every row retried
    in the pass is stamped with that same ``now``; ties retry in address order.
    """
    if retry_hours <= 0 or batch <= 0:
        return {"retried": 0, "resolved": 0}

    if now is None:
        now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=retry_hours)
    rows = (
        await session.scalars(
            select(GeocodeCache)
            .where(GeocodeCache.latitude.is_(None), GeocodeCache.last_attempted_at < cutoff)
            .order_by(GeocodeCache.last_attempted_at, GeocodeCache.address)
            .limit(batch)
        )
    ).all()

    resolved = 0
    for row in rows:
        coords = await geocoder.geocode(row.address)
        row.last_attempted_at = now
        if coords is not None:
            row.latitude, row.longitude = coords
            resolved += 1
            await session.execute(
                update(Event)
                .where(Event.address == row.address, Event.location.is_(None))
                .values(location=ewkt_point(*coords))
            )
    await session.commit()
    return {"retried": len(rows), "resolved": resolved}


async def run_sources(
    session: AsyncSession,
    sources: list[EventSource],
    geocoder: Geocoder | None = None,
    max_miles: float = 0,
    *,
    blocked_tags: Collection[str] = frozenset(),
    center: Coords | None = None,
    now: datetime | None = None,
) -> dict[str, int]:
    """Fetch every source and persist the combined result.

    A failure in one source does not abort the others. ``blocked_tags``,
    ``center`` and ``now`` are forwarded to upsert_raw_events.
    """
    raws: list[RawEvent] = []
    for source in sources:
        try:
            raws.extend(await source.fetch())
        except Exception:  # noqa: BLE001 — defensive against flaky feeds
            log.exception("event source %s failed", getattr(source, "name", source))
    return await upsert_raw_events(
        session,
        raws,
        geocoder,
        max_miles=max_miles,
        blocked_tags=blocked_tags,
        center=center,
        now=now,
    )
