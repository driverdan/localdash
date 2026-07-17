"""FastAPI application: REST API + WebSocket + static dashboard + poll scheduler."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette.types import Scope

from app.api import events, news, root, timeseries, weather
from app.config import get_settings
from app.db import SessionLocal
from app.news.registry import sync_registry
from app.scheduler import build_scheduler

logging.basicConfig(level=logging.INFO)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


class NoCacheStaticFiles(StaticFiles):
    """Serve static assets with `Cache-Control: no-cache`, plus an SPA fallback.

    The dashboard has no build step / content hashing, so a stale cached app.js
    after a redeploy silently runs old code. `no-cache` forces the browser to
    revalidate via ETag every load — unchanged files still return a cheap 304,
    but new code is always picked up.

    The SPA has client-side routes (e.g. /map), so an extension-less path that
    matches no file serves index.html and lets the router take over. Asset
    paths (with an extension) still 404 loudly, and /api never falls back —
    unmatched API paths land here because this mount catches everything.
    """

    async def get_response(self, path: str, scope: Scope):
        try:
            response = await super().get_response(path, scope)
        except HTTPException as exc:
            # StaticFiles raises (not returns) its 404s.
            if exc.status_code != 404 or path.startswith("api/") or "." in path.rsplit("/", 1)[-1]:
                raise
            response = await super().get_response("index.html", scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    # The news feed registry is code (app/news/registry.py); mirror it into the
    # DB before the scheduler's first fetch. Migrations have already run by now
    # (compose runs `alembic upgrade head` before serving; local dev does too).
    async with SessionLocal() as session:
        await sync_registry(session)
    scheduler, collectors = build_scheduler()
    app.state.collectors = collectors
    app.state.scheduler = scheduler
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(title="LocalDash", version="0.1.0", lifespan=lifespan)
# Each feature owns a namespace under /api/v1/<feature>/; app-shell routes
# (feature-agnostic, e.g. /config) sit directly under /api/v1.
app.include_router(timeseries.router, prefix="/api/v1/timeseries")
app.include_router(news.router, prefix="/api/v1/news")
app.include_router(events.router, prefix="/api/v1/events")
if get_settings().weather_enabled:
    app.include_router(weather.router, prefix="/api/v1/weather")
app.include_router(root.router, prefix="/api/v1")

# Serve the dashboard at / (mounted last so /api wins).
app.mount("/", NoCacheStaticFiles(directory=STATIC_DIR, html=True), name="static")
