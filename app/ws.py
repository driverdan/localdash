"""WebSocket connection manager — broadcasts live-update messages to dashboards.

One global bus at /api/v1/ws (see app/api/root.py): every connected client
receives every message and filters by the `topic` field client-side. Messages
are either timeseries diffs (data) or per-feature invalidation pings.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send to every connected client, dropping broken connections."""
        async with self._lock:
            targets = list(self._clients)

        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001 — drop broken connections
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients.discard(ws)

    async def ping(self, topic: str) -> None:
        """Broadcast a payload-free invalidation ping: clients refetch via REST."""
        await self.broadcast({"topic": topic, "type": "updated"})


manager = ConnectionManager()
