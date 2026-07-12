"""Address geocoding.

Sources provide street addresses; the ingest pipeline uses a :class:`Geocoder`
to resolve them to coordinates (results are cached in the database — see
``app.events.ingest``). The default implementation uses the public
OpenStreetMap Nominatim service, whose usage policy requires a descriptive
User-Agent and limits request rates; the permanent DB cache keeps steady-state
volume near zero (no additional throttling yet — see the change's design doc).
"""
from __future__ import annotations

import logging
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
    ):
        self.base_url = base_url
        self.user_agent = user_agent
        self.timeout = timeout

    async def geocode(self, address: str) -> Coords | None:
        if not address:
            return None
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
