"""Background refresh scheduling: composes jobs, contains no cycle logic.

`job_specs()` lists every scheduled job (one per collector, plus news, events
and weather); `build_scheduler()` registers the enabled ones in one loop with
the shared options; `_run_job()` is the one error-logging wrapper around every
job. Each refresh cycle (its lock, session and signal) lives beside the code it
drives: app/collect.py, app/news/refresh.py, app/events/refresh.py and
app/weather/refresh.py. The scheduled and manual triggers call the same entry
points.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.collect import run_collector
from app.collectors.base import BaseCollector
from app.config import Settings
from app.events.refresh import refresh as events_refresh
from app.news.refresh import refresh as news_refresh
from app.weather.refresh import refresh as weather_refresh

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class JobSpec:
    """One scheduled job: what to call, with what, how often, and whether at all."""

    id: str
    func: Callable[..., Awaitable[object]]
    interval_seconds: int
    enabled: bool = True
    args: tuple = ()


def job_specs(settings: Settings, collectors: Mapping[str, BaseCollector]) -> list[JobSpec]:
    """Every scheduled job, disabled ones included (enabled=False). Pure."""
    specs = [
        JobSpec(
            id=collector.source_key,
            func=run_collector,
            interval_seconds=collector.poll_interval,
            args=(collector,),
        )
        for collector in collectors.values()
    ]
    specs += [
        JobSpec(
            id="news_refresh",
            func=news_refresh,
            interval_seconds=settings.news_refresh_minutes * 60,
            enabled=settings.news_enabled,
        ),
        JobSpec(
            id="events_refresh",
            func=events_refresh,
            interval_seconds=settings.events_refresh_minutes * 60,
            enabled=settings.events_enabled,
        ),
        JobSpec(
            id="weather_refresh",
            func=weather_refresh,
            interval_seconds=settings.weather_cache_minutes * 60,
            enabled=settings.weather_enabled,
        ),
    ]
    return specs


async def _run_job(spec: JobSpec) -> None:
    """Run one job's cycle; a failure only logs (the next tick retries)."""
    try:
        await spec.func(*spec.args)
    except Exception:  # noqa: BLE001
        log.exception("refresh job %s failed", spec.id)


def build_scheduler(specs: list[JobSpec]) -> AsyncIOScheduler:
    """Register every enabled spec with the shared options; not started."""
    scheduler = AsyncIOScheduler(timezone="UTC")
    for spec in specs:
        if not spec.enabled:
            continue
        scheduler.add_job(
            _run_job,
            "interval",
            seconds=spec.interval_seconds,
            args=[spec],
            id=spec.id,
            name=spec.id,  # APScheduler logs the name; otherwise every job reads "_run_job"
            next_run_time=datetime.now(timezone.utc),  # run once immediately on startup
            max_instances=1,
            coalesce=True,
        )
    return scheduler
