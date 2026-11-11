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

from app.http import make_client

log = logging.getLogger(__name__)

Coords = tuple[float, float]


def _candidate_queries(address: str) -> list[str]:
    """Ordered free-form queries to try for an address, most specific first.

    Feed addresses look like "Venue Name, street, city, ST, zip, country";
    Nominatim's free-form search usually fails on the venue-name prefix. After
    the full string we try it with the leading component stripped, then the
    locality tail alone (city-centroid precision — acceptable for this app's
    distance granularity). Component thresholds keep short, already-plain
    addresses from being stripped past usefulness.
    """
    parts = [p.strip() for p in address.split(",") if p.strip()]
    candidates = [address]
    if len(parts) >= 4:
        candidates.append(", ".join(parts[1:]))
    if len(parts) >= 5:
        candidates.append(", ".join(parts[-4:]))
    seen: set[str] = set()
    return [c for c in candidates if not (c in seen or seen.add(c))]


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
    """Nominatim lookups over one HTTP client held for the geocoder's lifetime.

    Use it as an async context manager: the client opens on enter and closes on
    exit, so every lookup in a refresh cycle shares one connection pool.
    ``geocode()`` outside the context raises rather than opening a client.
    """

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
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> NominatimGeocoder:
        if self._client is not None:
            raise RuntimeError("NominatimGeocoder is already open")
        self._client = make_client(
            timeout=self.timeout, user_agent=self.user_agent, follow_redirects=False
        )
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        client, self._client = self._client, None
        if client is not None:
            await client.aclose()

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
        client = self._client
        if client is None:
            raise RuntimeError("NominatimGeocoder.geocode() called outside `async with`")
        if not address:
            return None
        # Try progressively simplified variants; only an empty result advances
        # to the next one. A network/service error aborts the whole lookup so
        # an outage doesn't multiply request volume across fallbacks.
        for query in _candidate_queries(address):
            await self._wait_for_slot()
            try:
                resp = await client.get(
                    self.base_url, params={"q": query, "format": "json", "limit": 1}
                )
                resp.raise_for_status()
                results = resp.json()
            except Exception:  # noqa: BLE001 — network/service failures resolve to None
                log.exception("geocoding failed for %r", query)
                return None
            if not results:
                continue
            try:
                return float(results[0]["lat"]), float(results[0]["lon"])
            except KeyError, ValueError, TypeError, IndexError:
                return None
        return None
