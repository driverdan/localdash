"""One events refresh cycle: fetch all configured sources, upsert, then retry
stale geocode failures.

A module-level lock serializes the scheduled job and the manual
POST /api/v1/events/refresh — APScheduler's max_instances=1 only covers the
scheduled path, so without this a manual refresh could interleave with it.
The geocode retry pass runs under the same lock so all Nominatim traffic in a
cycle shares one rate-limited geocoder.
"""

from __future__ import annotations

import asyncio
import logging

from app.config import get_settings
from app.db import SessionLocal
from app.events.geocoding import NominatimGeocoder
from app.events.ingest import reconcile_events, retry_failed_geocodes, run_sources
from app.events.schemas import EventsRefreshResult
from app.events.sources import build_sources
from app.ws import manager

log = logging.getLogger("localdash.events")

_refresh_lock = asyncio.Lock()


async def refresh() -> EventsRefreshResult:
    """Fetch all configured sources and upsert; safe to call concurrently."""
    settings = get_settings()
    async with _refresh_lock:
        sources = build_sources(settings)
        # One geocoder (and so one HTTP client) for the whole cycle: source
        # ingest and the retry pass share its connection pool and rate limit.
        async with (
            NominatimGeocoder(
                user_agent=settings.events_geocoder_user_agent,
                min_interval=settings.events_geocoder_min_interval_seconds,
            ) as geocoder,
            SessionLocal() as session,
        ):
            upserted = await run_sources(
                session,
                sources,
                geocoder,
                max_miles=settings.events_ingest_max_miles,
                blocked_tags=settings.blocked_tags,
                center=settings.center,
            )
            retry = await retry_failed_geocodes(
                session,
                geocoder,
                retry_hours=settings.events_geocode_retry_hours,
                batch=settings.events_geocode_retry_batch,
            )
            # After the retry pass so freshly resolved coordinates can
            # satisfy the matcher's location gate this same cycle.
            reconciled = await reconcile_events(session)
        result = EventsRefreshResult(
            created=upserted.created,
            merged=upserted.merged,
            skipped_far=upserted.skipped_far,
            retried=retry.retried,
            resolved=retry.resolved,
            reconciled=reconciled,
        )
        log.info(
            "events refresh done: %d sources, %d created, %d merged, %d skipped far, "
            "%d geocodes retried (%d resolved), %d reconciled",
            len(sources),
            result.created,
            result.merged,
            result.skipped_far,
            result.retried,
            result.resolved,
            result.reconciled,
        )
        # Ping only when the cycle changed data clients can see; a cycle that
        # merely re-fetched unchanged sources stays silent.
        if result.changed_visible_data:
            await manager.ping("events")
        return result
