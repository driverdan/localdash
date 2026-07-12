"""Address geocoding.

Sources provide street addresses; the ingest pipeline uses a :class:`Geocoder`
to resolve them to coordinates (results are cached in the database — see
``app.events.ingest``). The default implementation uses the public
OpenStreetMap Nominatim service, whose usage policy requires a descriptive
User-Agent and caps clients at 1 request/second; outbound requests are spaced
by ``min_interval`` accordingly, and the permanent DB cache keeps steady-state
volume near zero.
"""
from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod

import httpx

log = logging.getLogger("localdash.events")

Coords = tuple[float, float]


class Geocoder(ABC):
    @abstractmethod
    async def geocode(self, address: str) -> Coords | None:
        """Resolve ``address`` to ``(latitude, longitude)`` or ``None``."""
        raise NotImplementedError


class NullGeocoder(Geocoder):
    """Resolves nothing. Used as a safe default when geocoding is not wanted."""

    async def geocode(self, address: str) -> Coords | None:
        return None


class NominatimGeocoder(Geocoder):
    def __init__(
        self,
        user_agent: str,
        base_url: str = "https://nominatim.openstreetmap.org/search",
        timeout: int = 10,
        min_interval: float = 1.0,
    ):
        self.base_url = base_url
        self.user_agent = user_agent
        self.timeout = timeout
        self.min_interval = min_interval
        self._slot_lock = asyncio.Lock()
        self._next_send = 0.0  # monotonic time before which no request may go out

    async def _wait_for_slot(self) -> None:
        """Claim the next send slot so requests are >= min_interval apart.

        The lock only guards the slot bookkeeping; the wait (and the request
        itself) happens outside it, so concurrent callers queue up spaced
        slots instead of serializing on request latency.
        """
        if self.min_interval <= 0:
            return
        async with self._slot_lock:
            slot = max(time.monotonic(), self._next_send)
            self._next_send = slot + self.min_interval
        delay = slot - time.monotonic()
        if delay > 0:
            await asyncio.sleep(delay)

    async def geocode(self, address: str) -> Coords | None:
        if not address:
            return None
        await self._wait_for_slot()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    self.base_url,
                    params={"q": address, "format": "json", "limit": 1},
                    headers={"User-Agent": self.user_agent},
                )
                resp.raise_for_status()
                results = resp.json()
        except Exception:  # noqa: BLE001 — network/service failures resolve to None
            log.exception("geocoding failed for %r", address)
            return None
        if not results:
            return None
        try:
            return float(results[0]["lat"]), float(results[0]["lon"])
        except (KeyError, ValueError, TypeError, IndexError):
            return None
