"""FastAPI application: REST API + WebSocket + static dashboard + poll scheduler."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from starlette.types import Scope

from app.api.routes import router
from app.scheduler import build_scheduler

logging.basicConfig(level=logging.INFO)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


class NoCacheStaticFiles(StaticFiles):
    """Serve static assets with `Cache-Control: no-cache`.

    The dashboard has no build step / content hashing, so a stale cached app.js
    after a redeploy silently runs old code. `no-cache` forces the browser to
    revalidate via ETag every load — unchanged files still return a cheap 304,
    but new code is always picked up.
    """

    async def get_response(self, path: str, scope: Scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler, collectors = build_scheduler()
    app.state.collectors = collectors
    app.state.scheduler = scheduler
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(title="LocalDash", version="0.1.0", lifespan=lifespan)
app.include_router(router, prefix="/api")

# Serve the dashboard at / (mounted last so /api wins).
app.mount("/", NoCacheStaticFiles(directory=STATIC_DIR, html=True), name="static")
