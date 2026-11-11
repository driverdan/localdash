"""Tests for app/http.py (the outbound client factory) and the test-suite HTTP guard."""

from __future__ import annotations

import ast
from pathlib import Path

import httpx
import pytest

import app.http
from app.config import Settings, get_settings
from app.http import BROWSER_USER_AGENT, make_client

APP_DIR = Path(__file__).parent.parent / "app"
HTTP_MODULE = APP_DIR / "http.py"


def _ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, text="ok")


# --- factory ---


async def test_default_user_agent_is_the_setting(mock_http):
    mock_http.install(_ok)
    async with make_client(timeout=5, follow_redirects=False) as client:
        await client.get("https://example.test/")

    assert mock_http.requests[0].headers["User-Agent"] == get_settings().user_agent


async def test_default_user_agent_is_read_when_the_client_is_built(mock_http, monkeypatch):
    # Not captured at import: a different Settings at build time is honoured.
    settings = Settings(_env_file=None, user_agent="Configured/2.0")
    monkeypatch.setattr(app.http, "get_settings", lambda: settings)
    mock_http.install(_ok)
    async with make_client(timeout=5, follow_redirects=False) as client:
        await client.get("https://example.test/")

    assert mock_http.requests[0].headers["User-Agent"] == "Configured/2.0"


async def test_explicit_user_agent_overrides_the_default(mock_http):
    mock_http.install(_ok)
    async with make_client(timeout=5, follow_redirects=False, user_agent="Agent/1.0") as client:
        await client.get("https://example.test/")

    assert mock_http.requests[0].headers["User-Agent"] == "Agent/1.0"


async def test_user_agent_none_is_the_default_not_httpx(mock_http):
    mock_http.install(_ok)
    async with make_client(timeout=5, follow_redirects=False, user_agent=None) as client:
        await client.get("https://example.test/")

    ua = mock_http.requests[0].headers["User-Agent"]
    assert ua == get_settings().user_agent
    assert ua.strip()
    assert not ua.startswith("python-httpx/")


@pytest.mark.parametrize("blank", ["", " ", "\t\n"])
def test_blank_user_agent_override_is_rejected(blank):
    with pytest.raises(ValueError, match="user_agent"):
        make_client(timeout=5, follow_redirects=False, user_agent=blank)


@pytest.mark.parametrize("follow", [True, False])
async def test_timeout_and_redirect_policy_are_applied(mock_http, follow):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/start":
            return httpx.Response(302, headers={"Location": "/end"})
        return httpx.Response(200)

    mock_http.install(handler)
    async with make_client(timeout=7.5, follow_redirects=follow) as client:
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
        timeout=5, follow_redirects=False, user_agent="Agent/1.0", headers={"Accept": "x/y"}
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
    async with make_client(timeout=5, follow_redirects=False) as client:
        resp = await client.get("https://example.test/x")

    assert resp.status_code == 204
    assert seen == ["https://example.test/x"]


def test_http_module_reads_only_the_user_agent_setting():
    # The factory's default User-Agent is the one setting app/http.py may read.
    tree = ast.parse(HTTP_MODULE.read_text())
    reads = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "get_settings"
    }
    assert reads == {"user_agent"}
    assert HTTP_MODULE.read_text().count("get_settings()") == 1


# --- default-deny guard ---


async def test_unmocked_request_is_refused_and_reported(_outbound_http):
    async with make_client(timeout=5, follow_redirects=False) as client:
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
            async with make_client(timeout=5, follow_redirects=False) as c:
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


# The only User-Agent overrides app/ may pass to make_client, by file, with the source
# text of the argument. Each is a UA its upstream requires (see the outbound-http spec);
# every other call site sends the default, the `user_agent` setting.
SANCTIONED_UA_OVERRIDES = {
    APP_DIR / "events" / "sources" / "carcruisefinder.py": "BROWSER_USER_AGENT",
    APP_DIR / "news" / "fetcher.py": "BROWSER_USER_AGENT",
    APP_DIR / "events" / "geocoding.py": "self.user_agent",
}


def _make_client_calls() -> list[tuple[Path, int, str | None]]:
    """(file, line, source of the user_agent= argument or None) for each make_client call."""
    calls = []
    for path in sorted(APP_DIR.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            if name != "make_client":
                continue
            ua = next((kw.value for kw in node.keywords if kw.arg == "user_agent"), None)
            calls.append((path, node.lineno, None if ua is None else ast.unparse(ua)))
    return calls


def test_user_agent_is_passed_only_by_the_sanctioned_overrides():
    calls = _make_client_calls()
    # Guard against the walk silently matching nothing.
    assert len(calls) >= 10
    passed = [(path, line, src) for path, line, src in calls if src is not None]
    assert not [c for c in passed if c[2] == "None"], "make_client(user_agent=None) is redundant"
    assert {path: src for path, _, src in passed} == SANCTIONED_UA_OVERRIDES, passed
    assert len(passed) == len(SANCTIONED_UA_OVERRIDES), passed
