"""One timeseries collection cycle, end to end.

`run_collector` drives a single collector through the pipeline: collector
(fetch + normalize, see app/collectors/) -> `ingest` -> diff broadcast on the
live-update bus -> `sources` telemetry. It is shared by the scheduled tick
(app/scheduler.py) and the manual POST /api/v1/timeseries/sources/{key}/refresh
endpoint, so both have the same effects.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.collectors.base import BaseCollector
from app.db import SessionLocal
from app.ingest import ingest
from app.models import Source
from app.redaction import redact
from app.timeseries_schemas import CollectorRun
from app.ws import manager

log = logging.getLogger(__name__)

# Per-source collection locks, created lazily (see run_collector).
_source_locks: dict[str, asyncio.Lock] = {}


def _source_lock(source_key: str) -> asyncio.Lock:
    """Per-source lock serializing scheduled and manual cycles of one collector."""
    lock = _source_locks.get(source_key)
    if lock is None:
        lock = _source_locks[source_key] = asyncio.Lock()
    return lock


async def run_collector(collector: BaseCollector) -> CollectorRun:
    """Run one collection cycle; persist telemetry; broadcast diff.

    Cycles for the same source are serialized: APScheduler's max_instances only
    covers scheduled ticks, so a manual /refresh during a tick would otherwise
    run a second concurrent ingest() over the same entities.
    """
    async with _source_lock(collector.source_key):
        status: Literal["ok", "error"] = "ok"
        error: str | None = None
        count = 0
        try:
            observations = await collector.collect()
            count = len(observations)
            async with SessionLocal() as session:
                diff = await ingest(session, collector.source_key, observations)
            if not diff.is_empty:
                await manager.broadcast(diff.to_message())
        except Exception as exc:
            # Persisted to sources.last_error and served by /sources: mask credentials.
            status, error = "error", redact(str(exc))
            log.exception("collector %s failed", collector.source_key)

        await _record_run(collector, status, error, count)
    return CollectorRun(source=collector.source_key, status=status, error=error, count=count)


async def _record_run(collector: BaseCollector, status: str, error: str | None, count: int) -> None:
    async with SessionLocal() as session:
        stmt = pg_insert(Source).values(
            key=collector.source_key,
            name=collector.name,
            enabled=True,
            poll_interval_seconds=collector.poll_interval,
            last_run_at=datetime.now(UTC),
            last_status=status,
            last_error=error,
            last_count=count,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[Source.key],
            set_={
                "name": collector.name,
                "poll_interval_seconds": collector.poll_interval,
                "last_run_at": stmt.excluded.last_run_at,
                "last_status": status,
                "last_error": error,
                "last_count": count,
            },
        )
        await session.execute(stmt)
        await session.commit()
