"""Outbound HTTP: the one place the app builds httpx clients for upstream services.

Every call site passes its timeout and redirect policy explicitly; neither has a
default, so each upstream's request settings are visible where it fetches (and a
change to them shows up in the diff). The User-Agent defaults to the app's
`user_agent` setting, read when the client is built; a call site passes
`user_agent=` only to override it with a different UA its upstream requires (the
browser UA, or the geocoder's own setting). Every client sends a non-empty
User-Agent: there is no way to send httpx's default (`python-httpx/<version>`).
`user_agent` is the only setting this module reads.
"""

from __future__ import annotations

from collections.abc import Mapping

import httpx

from app.config import get_settings

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
    follow_redirects: bool,
    user_agent: str | None = None,
    headers: Mapping[str, str] | None = None,
) -> httpx.AsyncClient:
    """Build an httpx client for an upstream fetch.

    `user_agent` omitted or None sends the app's `user_agent` setting. Pass one only
    to override it; a blank override raises `ValueError`. `headers` are extra
    client-level default headers; per-request headers stay at the call site.
    """
    if user_agent is None:
        user_agent = get_settings().user_agent
    elif not user_agent.strip():
        raise ValueError("make_client: user_agent override must not be blank")
    client_headers: dict[str, str] = dict(headers or {})
    client_headers["User-Agent"] = user_agent
    return httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=follow_redirects,
        headers=client_headers,
        transport=_transport,
    )
