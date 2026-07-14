"""WebSocket connection manager — broadcasts ingest diffs to live dashboards."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._clients: dict[WebSocket, str | None] = {}
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket, source: str | None = None) -> None:
        await ws.accept()
        async with self._lock:
            self._clients[ws] = source

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.pop(ws, None)

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send to every client subscribed to this source (or to all sources)."""
        src = message.get("source")
        async with self._lock:
            targets = [ws for ws, sub in self._clients.items() if sub in (None, src)]

        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001 — drop broken connections
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients.pop(ws, None)


manager = ConnectionManager()
