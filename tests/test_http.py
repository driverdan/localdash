"""Tests for app/http.py (the outbound client factory) and the test-suite HTTP guard."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

import app.http
from app.http import BROWSER_USER_AGENT, make_client

APP_DIR = Path(__file__).parent.parent / "app"
HTTP_MODULE = APP_DIR / "http.py"


def _ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, text="ok")


# --- factory ---


async def test_user_agent_string_is_sent(mock_http):
    mock_http.install(_ok)
    async with make_client(timeout=5, user_agent="Agent/1.0", follow_redirects=False) as client:
        await client.get("https://example.test/")

    assert mock_http.requests[0].headers["User-Agent"] == "Agent/1.0"


async def test_user_agent_none_sends_the_httpx_default(mock_http):
    mock_http.install(_ok)
    async with make_client(timeout=5, user_agent=None, follow_redirects=False) as client:
        await client.get("https://example.test/")

    assert mock_http.requests[0].headers["User-Agent"] == f"python-httpx/{httpx.__version__}"


@pytest.mark.parametrize("follow", [True, False])
async def test_timeout_and_redirect_policy_are_applied(mock_http, follow):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/start":
            return httpx.Response(302, headers={"Location": "/end"})
        return httpx.Response(200)

    mock_http.install(handler)
    async with make_client(timeout=7.5, user_agent=None, follow_redirects=follow) as client:
        assert client.follow_redirects is follow
        resp = await client.get("https://example.test/start")

    assert resp.status_code == (200 if follow else 302)
    assert [r.url.path for r in mock_http.requests] == (
        ["/start", "/end"] if follow else ["/start"]
    )
    assert mock_http.requests[0].extensions["timeout"] == {
        "connect": 7.5,
        "read": 7.5,
        "write": 7.5,
        "pool": 7.5,
    }


async def test_extra_headers_are_merged_with_the_user_agent(mock_http):
    mock_http.install(_ok)
    async with make_client(
        timeout=5, user_agent="Agent/1.0", follow_redirects=False, headers={"Accept": "x/y"}
    ) as client:
        await client.get("https://example.test/", headers={"X-Per-Request": "1"})

    headers = mock_http.requests[0].headers
    assert headers["User-Agent"] == "Agent/1.0"
    assert headers["Accept"] == "x/y"
    assert headers["X-Per-Request"] == "1"


async def test_transport_override_is_used(monkeypatch):
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(204)

    monkeypatch.setattr(app.http, "_transport", httpx.MockTransport(handler))
    async with make_client(timeout=5, user_agent=None, follow_redirects=False) as client:
        resp = await client.get("https://example.test/x")

    assert resp.status_code == 204
    assert seen == ["https://example.test/x"]


def test_http_module_reads_no_settings():
    assert "app.config" not in HTTP_MODULE.read_text()


# --- default-deny guard ---


async def test_unmocked_request_is_refused_and_reported(_outbound_http):
    async with make_client(timeout=5, user_agent=None, follow_redirects=False) as client:
        with pytest.raises(httpx.ConnectError):
            await client.get("https://unmocked.example/path")

    report = _outbound_http.unmocked_report()
    assert report is not None
    assert "https://unmocked.example/path" in report
    # Clear it so this test's own teardown guard doesn't fail the test.
    _outbound_http.unmocked.clear()


async def test_swallowed_unmocked_request_is_still_reported(_outbound_http):
    async def isolated_fetch() -> None:
        try:
            async with make_client(timeout=5, user_agent=None, follow_redirects=False) as c:
                await c.get("https://swallowed.example/")
        except Exception:  # noqa: BLE001 — mimics per-source failure isolation
            pass

    await isolated_fetch()

    report = _outbound_http.unmocked_report()
    assert report is not None and "https://swallowed.example/" in report
    _outbound_http.unmocked.clear()


def test_no_unmocked_requests_means_no_report(mock_http):
    assert mock_http.unmocked_report() is None


# --- static rules over the app package ---


def _app_files_containing(needle: str) -> list[Path]:
    return sorted(p for p in APP_DIR.rglob("*.py") if needle in p.read_text())


def test_async_client_is_only_constructed_in_app_http():
    assert _app_files_containing("httpx.AsyncClient(") == [HTTP_MODULE]


def test_browser_user_agent_literal_is_only_in_app_http():
    assert _app_files_containing(BROWSER_USER_AGENT) == [HTTP_MODULE]
    assert _app_files_containing("Gecko/20100101") == [HTTP_MODULE]
