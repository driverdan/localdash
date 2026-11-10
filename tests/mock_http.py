"""Shared outbound-HTTP mock for tests.

`conftest.py` installs one :class:`MockHTTP` per test into ``app.http._transport``,
so every client built by ``app.http.make_client`` sends through it. With no handler
installed it denies: the request is recorded as unmocked and raises
``httpx.ConnectError``, and the test fails at teardown naming the URL (even when
the code under test swallowed the error). Tests take the ``mock_http`` fixture and
call :meth:`MockHTTP.install` with a handler to answer requests.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable

import httpx

Handler = Callable[[httpx.Request], httpx.Response | Awaitable[httpx.Response]]


class MockHTTP:
    """Records every request sent; answers them with the installed handler."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.unmocked: list[httpx.Request] = []
        self._handler: Handler | None = None
        self.transport = httpx.MockTransport(self._dispatch)

    def install(self, handler: Handler) -> MockHTTP:
        """Answer requests with ``handler`` (sync or async) from now on."""
        self._handler = handler
        return self

    async def _dispatch(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self._handler is None:
            self.unmocked.append(request)
            raise httpx.ConnectError(
                f"unmocked outbound request to {request.url} (use the mock_http fixture)",
                request=request,
            )
        response = self._handler(request)
        if inspect.isawaitable(response):
            response = await response
        return response

    def unmocked_report(self) -> str | None:
        """A failure message listing unmocked requests, or None if there were none."""
        if not self.unmocked:
            return None
        urls = "\n".join(f"  {r.method} {r.url}" for r in self.unmocked)
        return (
            "test sent outbound HTTP request(s) without a mock; install a handler "
            f"with the mock_http fixture:\n{urls}"
        )
