"""Unit tests for the WebSocket ConnectionManager (no real sockets)."""
from __future__ import annotations

import pytest

from app.ws import ConnectionManager


class FakeWS:
    """Minimal stand-in for starlette's WebSocket."""

    def __init__(self, fail: bool = False):
        self.accepted = False
        self.sent: list[dict] = []
        self._fail = fail

    async def accept(self):
        self.accepted = True

    async def send_json(self, msg):
        if self._fail:
            raise RuntimeError("connection broken")
        self.sent.append(msg)


async def test_connect_accepts_and_registers():
    mgr = ConnectionManager()
    ws = FakeWS()
    await mgr.connect(ws, source="hc911")
    assert ws.accepted
    assert ws in mgr._clients


async def test_broadcast_respects_source_subscription():
    mgr = ConnectionManager()
    hc911 = FakeWS()
    everything = FakeWS()
    aprs = FakeWS()
    await mgr.connect(hc911, source="hc911")
    await mgr.connect(everything, source=None)  # subscribes to all
    await mgr.connect(aprs, source="aprs")

    msg = {"type": "diff", "source": "hc911", "new": [], "updated": [], "closed": []}
    await mgr.broadcast(msg)

    assert hc911.sent == [msg]
    assert everything.sent == [msg]
    assert aprs.sent == []  # different source


async def test_broadcast_drops_dead_clients():
    mgr = ConnectionManager()
    good = FakeWS()
    dead = FakeWS(fail=True)
    await mgr.connect(good, source=None)
    await mgr.connect(dead, source=None)

    await mgr.broadcast({"source": "hc911"})

    assert good.sent  # delivered
    assert dead not in mgr._clients  # pruned after failure
    assert good in mgr._clients


async def test_disconnect_removes_client():
    mgr = ConnectionManager()
    ws = FakeWS()
    await mgr.connect(ws, source=None)
    await mgr.disconnect(ws)
    assert ws not in mgr._clients
    # idempotent
    await mgr.disconnect(ws)


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
