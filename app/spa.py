"""Serving the built single-page app: static assets, SPA fallback, site-name injection.

`app.main` mounts `NoCacheStaticFiles` over `STATIC_DIR` at `/`, last, so the
API routes win. This module depends only on Starlette/FastAPI and the standard
library; the site name is passed in rather than read from settings.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse, Response
from starlette.types import Receive, Scope, Send

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

# index.html carries this placeholder in two spots — the <title> text and the
# window.__SITE_NAME__ string literal — which are substituted with the configured
# site name at serve time (see NoCacheStaticFiles._index_html). Distinct from the
# __SITE_NAME__ property name so a naive replace can't clobber the global's identifier.
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


class NoCacheStaticFiles(StaticFiles):
    """Serve static assets with `Cache-Control: no-cache`, plus an SPA fallback.

    `index.html` is not content-hashed, so a cached copy after a redeploy would
    keep loading the old bundle. `no-cache` forces the browser to revalidate via
    ETag every load — unchanged files still return a cheap 304, but new code is
    always picked up.

    The SPA has client-side routes (e.g. /map), so an extension-less path that
    matches no file serves index.html and lets the router take over. Asset
    paths (with an extension) still 404 loudly, and /api never falls back —
    unmatched API paths land here because this mount catches everything.
    """

    def __init__(self, *args: Any, site_name: str, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._site_name = site_name
        self._index: str | None = None

    def _index_html(self) -> str:
        """The built index.html with the runtime site name substituted in.

        The name is fixed for the instance's lifetime, so this is computed once,
        on first use (never in `__init__`, so an empty static dir doesn't fail at
        import). It is escaped per context: HTML-escaped inside <title>, and
        embedded as a safe JS string literal for the window.__SITE_NAME__ global,
        so a name with <, ", or </script> can't break out of either.
        """
        if self._index is None:
            if self.directory is None:  # StaticFiles allows packages-only; this mount never is
                raise TypeError("NoCacheStaticFiles needs a directory to serve index.html from")
            raw = (Path(self.directory) / "index.html").read_text(encoding="utf-8")
            name = self._site_name
            # JS string-literal context first (matches the quoted placeholder incl. quotes).
            raw = raw.replace(f'"{SITE_NAME_TOKEN}"', _js_string(name))
            # Whatever token remains is the <title> text node.
            self._index = raw.replace(SITE_NAME_TOKEN, html.escape(name))
        return self._index

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Websocket upgrades on unmatched paths (e.g. an old bundle retrying the
        # removed /api/v1/timeseries/ws) land on this catch-all mount, which only
        # speaks http; close them cleanly instead of tracebacking per attempt.
        if scope["type"] == "websocket":
            await send({"type": "websocket.close"})
            return
        await super().__call__(scope, receive, send)

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            # The root request resolves to index.html via html=True; serve the
            # site-name-injected copy instead of the raw file. Starlette normpaths
            # the empty root path to ".", so match that too.
            if path in ("", ".", "index.html"):
                response: Response = HTMLResponse(self._index_html())
            else:
                response = await super().get_response(path, scope)
        except HTTPException as exc:
            # StaticFiles raises (not returns) its 404s.
            # Starlette normalizes bare /api and /api/ to "api", so match it too.
            is_api = path == "api" or path.startswith("api/")
            if exc.status_code != 404 or is_api or "." in path.rsplit("/", 1)[-1]:
                raise
            # SPA fallback for a client-side route — same injected index.html.
            response = HTMLResponse(self._index_html())
        response.headers["Cache-Control"] = "no-cache"
        return response
