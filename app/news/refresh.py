"""One news refresh cycle: fetch all feeds, then recluster.

A module-level lock serializes the scheduled job and the manual
POST /api/v1/news/refresh — APScheduler's max_instances=1 only covers the
scheduled path, so without this a manual refresh could interleave with it.
"""

from __future__ import annotations

import asyncio
import logging

from app.db import SessionLocal
from app.news.clustering import recluster
from app.news.fetcher import fetch_all

log = logging.getLogger("localdash.news")

_refresh_lock = asyncio.Lock()


async def refresh() -> dict:
    """Fetch all feeds and recluster; safe to call concurrently."""
    async with _refresh_lock:
        async with SessionLocal() as session:
            results = await fetch_all(session)
            cluster_count = await recluster(session)
        log.info("news refresh done: %d clusters", cluster_count)
        return {"sources": results, "clusters": cluster_count}
