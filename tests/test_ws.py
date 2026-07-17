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
    await mgr.connect(ws)
    assert ws.accepted
    assert ws in mgr._clients


async def test_broadcast_reaches_every_client():
    mgr = ConnectionManager()
    a = FakeWS()
    b = FakeWS()
    await mgr.connect(a)
    await mgr.connect(b)

    msg = {
        "topic": "timeseries",
        "type": "diff",
        "source": "hc911",
        "new": [],
        "updated": [],
        "closed": [],
    }
    await mgr.broadcast(msg)

    assert a.sent == [msg]
    assert b.sent == [msg]


async def test_ping_broadcasts_topic_envelope():
    mgr = ConnectionManager()
    ws = FakeWS()
    await mgr.connect(ws)

    await mgr.ping("news")

    assert ws.sent == [{"topic": "news", "type": "updated"}]


async def test_broadcast_drops_dead_clients():
    mgr = ConnectionManager()
    good = FakeWS()
    dead = FakeWS(fail=True)
    await mgr.connect(good)
    await mgr.connect(dead)

    await mgr.broadcast({"topic": "timeseries", "source": "hc911"})

    assert good.sent  # delivered
    assert dead not in mgr._clients  # pruned after failure
    assert good in mgr._clients


async def test_disconnect_removes_client():
    mgr = ConnectionManager()
    ws = FakeWS()
    await mgr.connect(ws)
    await mgr.disconnect(ws)
    assert ws not in mgr._clients
    # idempotent
    await mgr.disconnect(ws)


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
