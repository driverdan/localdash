"""Keep upstream credentials out of logs and stored error strings.

Some upstreams only accept their key as a query parameter (AirNow's
``API_KEY``), so the key is part of the request URL — and httpx puts that URL
into its own INFO request log and into ``HTTPStatusError`` messages, which end
up in tracebacks. Rather than guarding every call site, this module scrubs
text at the two places it leaves the process:

- ``redact(text)`` masks the values of secret-looking query parameters and the
  literal values of the configured credentials. Use it on any exception text
  that is persisted or returned (e.g. ``sources.last_error``).
- ``install()`` wraps the logging LogRecord factory so every record is redacted
  as it is created — message, %-args, formatted traceback and stack — before
  any handler (root, uvicorn's, pytest's caplog) sees it. A factory rather
  than a handler filter, because filters only run on the handlers they are
  attached to, and handlers added later would silently miss it.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from contextvars import ContextVar
from urllib.parse import quote

REDACTED = "[REDACTED]"

_loading_settings: ContextVar[bool] = ContextVar("_loading_settings", default=False)

# Settings fields holding upstream credentials; their literal values are masked
# wherever they appear (headers echoed in errors, URLs, reprs).
SECRET_SETTINGS = ("airnow_api_key", "events_meetup_token", "hc911_auth_token", "tdot_api_key")
# Shorter values are not masked literally: too likely to collide with ordinary text.
_MIN_SECRET_LEN = 8

# A query parameter whose name says it carries a credential. Names are matched
# case-insensitively with optional _ / - separators (API_KEY, apiKey, access-token).
_SECRET_PARAM = re.compile(
    r"(?i)([?&;](?:api[_-]?key|key|token|access[_-]?token|auth|password|secret"
    r"|client[_-]?secret|signature|sig)=)[^&#\s'\"<>]+"
)


def _secret_values() -> list[str]:
    # Re-entrancy guard: building Settings can itself log (python-dotenv warns
    # on unparsable .env lines), which would recurse back in here before the
    # get_settings() cache is populated.
    if _loading_settings.get():
        return []
    token = _loading_settings.set(True)
    try:
        from app.config import get_settings

        settings = get_settings()
    except Exception:  # noqa: BLE001 — redaction must never break logging
        return []
    finally:
        _loading_settings.reset(token)
    values: set[str] = set()
    for field in SECRET_SETTINGS:
        value = getattr(settings, field, "") or ""
        if len(value) >= _MIN_SECRET_LEN:
            values.add(value)
            values.add(quote(value, safe=""))  # as it appears percent-encoded in a URL
    # Longest first so a value containing another is masked whole.
    return sorted(values, key=len, reverse=True)


def redact(text: str) -> str:
    """``text`` with credential query-param values and configured secrets masked."""
    if not text:
        return text
    text = _SECRET_PARAM.sub(rf"\1{REDACTED}", text)
    for value in _secret_values():
        text = text.replace(value, REDACTED)
    return text


def _redact_arg(arg: object) -> object:
    """A %-format argument, replaced by its redacted string only if it leaks.

    Clean arguments keep their type so formats like %d and consumers that
    unpack ``record.args`` (uvicorn's access formatter) keep working.
    """
    if isinstance(arg, (int, float, bool)) or arg is None:
        return arg
    try:
        text = str(arg)
    except Exception:  # noqa: BLE001
        return arg
    cleaned = redact(text)
    return arg if cleaned == text else cleaned


def redact_record(record: logging.LogRecord) -> logging.LogRecord:
    """Redact a LogRecord in place (message, args, traceback, stack)."""
    if isinstance(record.msg, str):
        record.msg = redact(record.msg)
    elif record.msg is not None:
        record.msg = _redact_arg(record.msg)
    if isinstance(record.args, Mapping):
        record.args = {k: _redact_arg(v) for k, v in record.args.items()}
    elif isinstance(record.args, tuple):
        record.args = tuple(_redact_arg(a) for a in record.args)
    if record.exc_info:
        # The traceback's last line is str(exc) — for httpx.HTTPStatusError that
        # embeds the full request URL. Pre-render it redacted into exc_text (which
        # Formatter uses verbatim) and drop exc_info so no formatter re-renders
        # the raw exception.
        if not record.exc_text:
            record.exc_text = logging.Formatter().formatException(record.exc_info)
        record.exc_info = None
    if record.exc_text:
        record.exc_text = redact(record.exc_text)
    if record.stack_info:
        record.stack_info = redact(record.stack_info)
    return record


def install() -> None:
    """Redact every LogRecord created from now on, process-wide. Idempotent."""
    current = logging.getLogRecordFactory()
    if getattr(current, "_localdash_redacting", False):
        return

    def factory(*args, **kwargs) -> logging.LogRecord:
        return redact_record(current(*args, **kwargs))

    factory._localdash_redacting = True  # type: ignore[attr-defined]
    logging.setLogRecordFactory(factory)
