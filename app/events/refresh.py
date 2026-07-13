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
from app.events.ingest import retry_failed_geocodes, run_sources
from app.events.sources import build_sources

log = logging.getLogger("localdash.events")

_refresh_lock = asyncio.Lock()


async def refresh() -> dict:
    """Fetch all configured sources and upsert; safe to call concurrently."""
    settings = get_settings()
    async with _refresh_lock:
        sources = build_sources(settings)
        geocoder = NominatimGeocoder(
            user_agent=settings.events_geocoder_user_agent,
            min_interval=settings.events_geocoder_min_interval_seconds,
        )
        async with SessionLocal() as session:
            stats = await run_sources(
                session, sources, geocoder, max_miles=settings.events_ingest_max_miles
            )
            stats |= await retry_failed_geocodes(
                session,
                geocoder,
                retry_hours=settings.events_geocode_retry_hours,
                batch=settings.events_geocode_retry_batch,
            )
        log.info(
            "events refresh done: %d sources, %d created, %d merged, %d skipped far, "
            "%d geocodes retried (%d resolved)",
            len(sources), stats["created"], stats["merged"], stats["skipped_far"],
            stats["retried"], stats["resolved"],
        )
        return stats
