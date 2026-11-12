"""FastAPI application: REST API + WebSocket + static dashboard + poll scheduler."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import auth, events, news, root, timeseries, weather
from app.collectors import build_collectors
from app.config import get_settings
from app.db import SessionLocal
from app.events.ingest import purge_blocked_tags
from app.news.registry import sync_registry
from app.redaction import install as install_log_redaction
from app.scheduler import build_scheduler, job_specs
from app.spa import STATIC_DIR, NoCacheStaticFiles

logging.basicConfig(level=logging.INFO)
# Mask credentials (e.g. AirNow's API_KEY query param, which httpx echoes in its
# request log and HTTPStatusError messages) in every log record from here on.
install_log_redaction()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # The news feed registry is code (app/news/registry.py); mirror it into the
    # DB before the scheduler's first fetch. Migrations have already run by now
    # (compose runs `alembic upgrade head` before serving; local dev does too).
    async with SessionLocal() as session:
        await sync_registry(session)
        # Purge blocklisted event tags before the first refresh re-tags events.
        await purge_blocked_tags(session, get_settings().blocked_tags)
    settings = get_settings()
    collectors = {c.source_key: c for c in build_collectors(settings)}
    app.state.collectors = collectors
    scheduler = build_scheduler(job_specs(settings, collectors))
    app.state.scheduler = scheduler
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(title=get_settings().site_name, version="0.1.0", lifespan=lifespan)
# Each feature owns a namespace under /api/v1/<feature>/; app-shell routes
# (feature-agnostic, e.g. /config) sit directly under /api/v1.
app.include_router(timeseries.router, prefix="/api/v1/timeseries")
app.include_router(news.router, prefix="/api/v1/news")
app.include_router(events.router, prefix="/api/v1/events")
if get_settings().weather_enabled:
    app.include_router(weather.router, prefix="/api/v1/weather")
app.include_router(auth.router, prefix="/api/v1/auth")
app.include_router(root.router, prefix="/api/v1")

# Serve the dashboard at / (mounted last so /api wins).
app.mount(
    "/",
    NoCacheStaticFiles(directory=STATIC_DIR, html=True, site_name=get_settings().site_name),
    name="static",
)
