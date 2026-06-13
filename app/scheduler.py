"""Background polling: one APScheduler job per enabled collector.

Each tick runs fetch -> normalize -> ingest -> broadcast, and records last-run
telemetry on the source row. Also used by the manual /refresh endpoint.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.collectors import build_collectors
from app.collectors.base import BaseCollector
from app.config import get_settings
from app.db import SessionLocal
from app.ingest import ingest
from app.models import Source
from app.ws import manager

log = logging.getLogger("localdash.scheduler")


async def run_collector(collector: BaseCollector) -> dict:
    """Run one collection cycle; persist telemetry; broadcast diff."""
    status, error, count = "ok", None, 0
    try:
        observations = await collector.collect()
        count = len(observations)
        async with SessionLocal() as session:
            diff = await ingest(session, collector.source_key, observations)
        if not diff.is_empty:
            await manager.broadcast(diff.to_message())
    except Exception as exc:  # noqa: BLE001
        status, error = "error", str(exc)
        log.exception("collector %s failed", collector.source_key)

    await _record_run(collector, status, error, count)
    return {"source": collector.source_key, "status": status, "error": error, "count": count}


async def _record_run(collector: BaseCollector, status: str, error: str | None, count: int) -> None:
    async with SessionLocal() as session:
        stmt = pg_insert(Source).values(
            key=collector.source_key,
            name=collector.name,
            enabled=True,
            poll_interval_seconds=collector.poll_interval,
            last_run_at=datetime.now(timezone.utc),
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


def build_scheduler() -> tuple[AsyncIOScheduler, dict[str, BaseCollector]]:
    settings = get_settings()
    collectors = {c.source_key: c for c in build_collectors(settings)}
    scheduler = AsyncIOScheduler(timezone="UTC")
    for collector in collectors.values():
        scheduler.add_job(
            run_collector,
            "interval",
            seconds=collector.poll_interval,
            args=[collector],
            id=collector.source_key,
            next_run_time=datetime.now(timezone.utc),  # run once immediately on startup
            max_instances=1,
            coalesce=True,
        )
    return scheduler, collectors
