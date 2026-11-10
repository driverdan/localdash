"""Offline tests for the SPA static mount (`app.spa.NoCacheStaticFiles`).

Each test mounts the class over a temporary directory holding a fixture
`index.html` and one asset, behind a bare app with a single API route. Nothing
here imports `app.main`, so neither a built `static/` nor a database is needed.
"""

from __future__ import annotations

import html
import json
import logging
from pathlib import Path

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.spa import SITE_NAME_TOKEN, NoCacheStaticFiles, _js_string

INDEX = (
    "<!doctype html><html><head>"
    f"<title>{SITE_NAME_TOKEN}</title>"
    f'<script>window.__SITE_NAME__ = "{SITE_NAME_TOKEN}"</script>'
    "</head><body><div id=app></div></body></html>"
)
# Carries the placeholder so a test can tell the asset is served raw, not injected.
ASSET = f'console.log("{SITE_NAME_TOKEN}");\n'
HOSTILE = '</script><script>alert(1)</script> & "q"'


@pytest.fixture
def static_dir(tmp_path: Path) -> Path:
    (tmp_path / "index.html").write_text(INDEX, encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text(ASSET, encoding="utf-8")
    return tmp_path


def _client(static_dir: Path, site_name: str = "Test Dash") -> TestClient:
    app = FastAPI()

    @app.get("/api/v1/ping")
    async def ping() -> dict[str, str]:
        return {"pong": "ok"}

    # Mounted last, as in app.main, so the API route wins.
    app.mount(
        "/",
        NoCacheStaticFiles(directory=static_dir, html=True, site_name=site_name),
        name="static",
    )
    return TestClient(app)


def _injected(site_name: str) -> str:
    return INDEX.replace(f'"{SITE_NAME_TOKEN}"', _js_string(site_name)).replace(
        SITE_NAME_TOKEN, html.escape(site_name)
    )


@pytest.mark.parametrize("path", ["/", "/index.html"])
def test_index_is_injected_with_no_cache(static_dir, path):
    r = _client(static_dir).get(path)
    assert r.status_code == 200
    assert r.headers["cache-control"] == "no-cache"
    assert r.headers["content-type"].startswith("text/html")
    assert r.text == _injected("Test Dash")
    assert "<title>Test Dash</title>" in r.text
    assert 'window.__SITE_NAME__ = "Test Dash"' in r.text
    assert SITE_NAME_TOKEN not in r.text


@pytest.mark.parametrize("path", ["/map", "/events/123"])
def test_client_routes_fall_back_to_injected_index(static_dir, path):
    r = _client(static_dir).get(path)
    assert r.status_code == 200
    assert r.headers["cache-control"] == "no-cache"
    assert r.text == _injected("Test Dash")


def test_missing_asset_is_404(static_dir):
    r = _client(static_dir).get("/assets/missing.js")
    assert r.status_code == 404
    assert "Test Dash" not in r.text


def test_built_asset_is_served_raw_with_no_cache(static_dir):
    r = _client(static_dir).get("/assets/app.js")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "no-cache"
    assert r.text == ASSET


@pytest.mark.parametrize("path", ["/api", "/api/", "/api/nope"])
def test_api_paths_never_fall_back_to_spa(static_dir, path):
    r = _client(static_dir).get(path)
    assert r.status_code == 404
    assert "<title>" not in r.text
    assert "Test Dash" not in r.text


def test_api_route_still_wins_over_mount(static_dir):
    r = _client(static_dir).get("/api/v1/ping")
    assert r.status_code == 200
    assert r.json() == {"pong": "ok"}


def test_hostile_site_name_is_escaped_per_context(static_dir):
    r = _client(static_dir, site_name=HOSTILE).get("/")
    assert r.status_code == 200
    assert f"<title>{html.escape(HOSTILE)}</title>" in r.text
    assert (
        "window.__SITE_NAME__ = "
        '"\\u003c/script\\u003e\\u003cscript\\u003ealert(1)\\u003c/script\\u003e \\u0026 \\"q\\""'
    ) in r.text
    # Only the fixture's own closing tag survives; the name never ends the script.
    assert r.text.count("</script>") == 1


def test_js_string_escapes_html_significant_characters():
    out = _js_string(HOSTILE)
    assert "<" not in out and ">" not in out and "&" not in out
    assert out == (
        '"\\u003c/script\\u003e\\u003cscript\\u003ealert(1)\\u003c/script\\u003e \\u0026 \\"q\\""'
    )
    # Still a valid JS/JSON string literal that decodes back to the original.
    assert json.loads(out) == HOSTILE


def test_index_is_read_once_per_instance(static_dir):
    client = _client(static_dir)
    first = client.get("/").text
    (static_dir / "index.html").write_text("<p>rewritten</p>", encoding="utf-8")
    assert client.get("/").text == first
    assert client.get("/map").text == first


def test_index_is_not_read_at_construction(tmp_path):
    # An empty static dir (as in CI) must not fail when the mount is built.
    NoCacheStaticFiles(directory=tmp_path, html=True, site_name="x")


def test_stray_websocket_is_closed_without_accepting(static_dir, caplog):
    client = _client(static_dir)
    with (
        caplog.at_level(logging.ERROR),
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect("/api/v1/timeseries/ws"),
    ):
        pass
    assert "Traceback" not in caplog.text
    assert not [rec for rec in caplog.records if rec.levelno >= logging.ERROR]
