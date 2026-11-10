"""Outbound HTTP: the one place the app builds httpx clients for upstream services.

Every call site passes its timeout, User-Agent and redirect policy explicitly; none of
them has a default, so each upstream's request settings are visible where it fetches
(and a change to them shows up in the diff). This module never reads app settings —
callers pass plain values.
"""

from __future__ import annotations

from collections.abc import Mapping

import httpx

# A mainstream browser User-Agent, for upstreams that punish anything else:
# TownNews (Local 3 feeds) returns 429 to unfamiliar UAs, and CarCruiseFinder
# returns 403 to short/script-like UAs. Define it here only; import it elsewhere.
BROWSER_USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"

# Test-only seam: the test suite sets this (via monkeypatch) to route every
# factory-built client through a mock transport. Production code never writes it;
# None means real HTTP.
_transport: httpx.AsyncBaseTransport | None = None


def make_client(
    *,
    timeout: float,
    user_agent: str | None,
    follow_redirects: bool,
    headers: Mapping[str, str] | None = None,
) -> httpx.AsyncClient:
    """Build an httpx client for an upstream fetch.

    `user_agent=None` deliberately sends httpx's default (`python-httpx/<version>`).
    `headers` are extra client-level default headers; per-request headers stay at the
    call site.
    """
    client_headers: dict[str, str] = dict(headers or {})
    if user_agent is not None:
        client_headers["User-Agent"] = user_agent
    return httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=follow_redirects,
        headers=client_headers,
        transport=_transport,
    )
