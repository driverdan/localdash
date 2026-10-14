"""Credentials never reach log output or stored error strings (app/redaction.py)."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
from uvicorn.logging import AccessFormatter

from app.config import get_settings
from app.redaction import REDACTED, install, redact

KEY = "0A1B2C3D-4E5F-6789-ABCD-EF0123456789"  # shaped like an AirNow key; fake
URL = (
    "https://www.airnowapi.org/aq/observation/latLong/current/"
    f"?format=application%2Fjson&latitude=35.0456&distance=25&API_KEY={KEY}"
)


@pytest.fixture(autouse=True)
def _redacting_logs(monkeypatch):
    install()
    monkeypatch.setenv("AIRNOW_API_KEY", KEY)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _status_error(url: str = URL, status: int = 410) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", url)
    response = httpx.Response(status, request=request)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        return exc
    raise AssertionError("expected HTTPStatusError")


def test_redact_masks_secret_query_params():
    out = redact(URL)
    assert KEY not in out
    assert f"API_KEY={REDACTED}" in out
    assert "latitude=35.0456" in out  # non-secret params untouched


@pytest.mark.parametrize("name", ["api_key", "apiKey", "token", "access_token", "key"])
def test_redact_masks_param_names_case_insensitively(name, monkeypatch):
    monkeypatch.setenv("AIRNOW_API_KEY", "")
    get_settings.cache_clear()
    out = redact(f"https://x.test/p?a=1&{name}=hunter2hunter2&b=2")
    assert "hunter2hunter2" not in out and "a=1" in out and "b=2" in out


def test_redact_masks_configured_secret_values_anywhere():
    # Not in a query string (e.g. an echoed header) — caught by literal match.
    assert KEY not in redact(f"upstream said: bad key {KEY!r}")


def test_redact_masks_http_status_error_message():
    # The exact shape that leaked: str(HTTPStatusError) embeds the full URL.
    assert KEY not in redact(str(_status_error()))


def test_logged_exception_traceback_is_redacted(caplog):
    log = logging.getLogger("localdash.test")
    try:
        raise _status_error()
    except httpx.HTTPStatusError:
        log.warning("AirNow AQI fetch failed", exc_info=True)
    assert KEY not in caplog.text
    assert "HTTPStatusError" in caplog.text  # the traceback itself is kept
    assert f"API_KEY={REDACTED}" in caplog.text


def test_logged_args_are_redacted(caplog):
    caplog.set_level(logging.INFO)
    logging.getLogger("httpx").info(
        'HTTP Request: %s %s "%s %d %s"', "GET", httpx.URL(URL), "HTTP/1.1", 410, "Gone"
    )
    assert KEY not in caplog.text
    assert "410 Gone" in caplog.text  # %d arg left intact


def test_clean_records_keep_their_args_for_uvicorn_access_log():
    """uvicorn's AccessFormatter unpacks record.args, so clean args must survive."""
    record = logging.getLogger("uvicorn.access").makeRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1:5000", "GET", "/api/v1/weather/current", "1.1", 200),
        None,
    )
    assert isinstance(record.args, tuple) and record.args[-1] == 200
    line = AccessFormatter("%(client_addr)s %(request_line)s %(status_code)s").format(record)
    assert "/api/v1/weather/current" in line and "200" in line


def test_install_is_idempotent():
    factory = logging.getLogRecordFactory()
    install()
    assert logging.getLogRecordFactory() is factory


def test_app_installs_redaction():
    """Importing the app (what uvicorn does) wires the factory — checked in a
    fresh interpreter, since this test process already called install()."""
    code = (
        "import logging, app.main; "
        "print(getattr(logging.getLogRecordFactory(), '_localdash_redacting', False))"
    )
    root = Path(__file__).resolve().parent.parent
    out = subprocess.run(
        [sys.executable, "-c", code], cwd=root, capture_output=True, text=True, check=True
    )
    assert out.stdout.strip().splitlines()[-1] == "True"
