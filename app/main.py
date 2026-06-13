"""FastAPI application: REST API + WebSocket + static dashboard + poll scheduler."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.scheduler import build_scheduler

logging.basicConfig(level=logging.INFO)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


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
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
