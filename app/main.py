"""FastAPI application: REST API + WebSocket + static dashboard + poll scheduler."""

from __future__ import annotations

import html
import json
import logging
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse, Response
from starlette.types import Scope

from app.api import events, news, root, timeseries, weather
from app.config import get_settings
from app.db import SessionLocal
from app.events.ingest import purge_blocked_tags
from app.news.registry import sync_registry
from app.scheduler import build_scheduler

logging.basicConfig(level=logging.INFO)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

# index.html carries this placeholder in two spots — the <title> text and the
# window.__SITE_NAME__ string literal — which are substituted with the configured
# site name at serve time (see _index_html). Distinct from the __SITE_NAME__
# property name so a naive replace can't clobber the global's identifier.
SITE_NAME_TOKEN = "__SITE_NAME_PLACEHOLDER__"


def _js_string(value: str) -> str:
    """A safe JS string literal for embedding in an inline <script>.

    JSON-encoding handles quotes/backslashes but leaves `<` intact, so a value
    containing `</script>` (or `<!--`) would terminate the script element in the
    HTML parser. Escape the HTML-significant characters to `\\uXXXX` so the value
    stays a valid JS string that can't break out of the tag.
    """
    encoded = json.dumps(value)
    return encoded.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


@lru_cache(maxsize=1)
def _index_html() -> str:
    """The built index.html with the runtime site name substituted in.

    The name is fixed for the process lifetime, so this is computed once. It is
    escaped per context: HTML-escaped inside <title>, and embedded as a safe JS
    string literal for the window.__SITE_NAME__ global, so a name with <, ", or
    </script> can't break out of either.
    """
    raw = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    name = get_settings().site_name
    # JS string-literal context first (matches the quoted placeholder incl. quotes).
    raw = raw.replace(f'"{SITE_NAME_TOKEN}"', _js_string(name))
    # Whatever token remains is the <title> text node.
    return raw.replace(SITE_NAME_TOKEN, html.escape(name))


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

    async def __call__(self, scope, receive, send):
        # Websocket upgrades on unmatched paths (e.g. an old bundle retrying the
        # removed /api/v1/timeseries/ws) land on this catch-all mount, which only
        # speaks http; close them cleanly instead of tracebacking per attempt.
        if scope["type"] == "websocket":
            await send({"type": "websocket.close"})
            return
        await super().__call__(scope, receive, send)

    async def get_response(self, path: str, scope: Scope):
        try:
            # The root request resolves to index.html via html=True; serve the
            # site-name-injected copy instead of the raw file. Starlette normpaths
            # the empty root path to ".", so match that too.
            if path in ("", ".", "index.html"):
                response: Response = HTMLResponse(_index_html())
            else:
                response = await super().get_response(path, scope)
        except HTTPException as exc:
            # StaticFiles raises (not returns) its 404s.
            if exc.status_code != 404 or path.startswith("api/") or "." in path.rsplit("/", 1)[-1]:
                raise
            # SPA fallback for a client-side route — same injected index.html.
            response = HTMLResponse(_index_html())
        response.headers["Cache-Control"] = "no-cache"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    # The news feed registry is code (app/news/registry.py); mirror it into the
    # DB before the scheduler's first fetch. Migrations have already run by now
    # (compose runs `alembic upgrade head` before serving; local dev does too).
    async with SessionLocal() as session:
        await sync_registry(session)
        # Purge blocklisted event tags before the first refresh re-tags events.
        await purge_blocked_tags(session)
    scheduler, collectors = build_scheduler()
    app.state.collectors = collectors
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
app.include_router(root.router, prefix="/api/v1")

# Serve the dashboard at / (mounted last so /api wins).
app.mount("/", NoCacheStaticFiles(directory=STATIC_DIR, html=True), name="static")
