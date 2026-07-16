"""Fetch + cache layer for the NWS proxy.

NWS is two-hop: /points/{lat},{lon} yields the gridpoint forecast URL and the
observation-stations URL. That metadata is static for a fixed coordinate, so
it is resolved lazily on first use and kept for the process lifetime (a failed
discovery is not kept — the next request retries). Steady state per cache
expiry is two calls: the forecast, and the latest observation from the nearest
station (falling back down the station list past null-temperature readings).

The shaped payload lives in an in-process TTL cache behind an asyncio lock, so
concurrent page loads coalesce into one upstream refresh. A failed refresh
serves the previous payload if one exists (its embedded timestamps mark its
age); a cold failure propagates for the router to turn into a 502.
"""

from __future__ import annotations

import asyncio
import logging
import time

import httpx

from app.config import Settings, get_settings
from app.weather.nws import parse_forecast, parse_observation, parse_points, parse_stations

log = logging.getLogger("localdash.weather")

POINTS_URL = "https://api.weather.gov/points/{lat},{lon}"
# Stations tried (nearest first) before giving up on current conditions.
STATION_LIMIT = 3


class WeatherService:
    # Test seam: offline tests set an httpx.MockTransport; None means real HTTP.
    _transport: httpx.AsyncBaseTransport | None = None

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._payload: dict | None = None
        self._fetched_at: float = 0.0
        # Per-process discovery result; None until the first successful /points hop.
        self._forecast_url: str | None = None
        self._station_urls: list[str] = []

    async def get_current(self) -> dict:
        """The shaped weather payload — cached, refreshed at most once per TTL."""
        settings = get_settings()
        ttl = settings.weather_cache_minutes * 60
        async with self._lock:
            if self._payload is not None and time.monotonic() - self._fetched_at < ttl:
                return self._payload
            try:
                payload = await self._refresh(settings)
            except Exception:
                if self._payload is None:
                    raise
                log.warning("weather refresh failed; serving stale payload", exc_info=True)
                return self._payload
            self._payload = payload
            self._fetched_at = time.monotonic()
            return payload

    def _make_client(self, settings: Settings) -> httpx.AsyncClient:
        # NWS asks for an identifying User-Agent; geo+json is its native shape.
        return httpx.AsyncClient(
            transport=self._transport,
            headers={"User-Agent": settings.user_agent, "Accept": "application/geo+json"},
            timeout=10.0,
            follow_redirects=True,
        )

    async def _refresh(self, settings: Settings) -> dict:
        async with self._make_client(settings) as client:
            if self._forecast_url is None or not self._station_urls:
                await self._discover(client, settings)
            periods, current = await asyncio.gather(
                self._fetch_periods(client),
                self._fetch_current(client),
            )
        # The two halves fail independently; only a fully empty refresh is an error.
        if periods is None and current is None:
            raise RuntimeError("both NWS fetches failed")
        return {"current": current, "periods": periods or []}

    async def _discover(self, client: httpx.AsyncClient, settings: Settings) -> None:
        response = await client.get(
            POINTS_URL.format(lat=settings.center_lat, lon=settings.center_lon)
        )
        response.raise_for_status()
        forecast_url, stations_url = parse_points(response.json())
        response = await client.get(stations_url)
        response.raise_for_status()
        stations = parse_stations(response.json(), STATION_LIMIT)
        if not stations:
            raise RuntimeError("NWS returned no observation stations")
        self._forecast_url, self._station_urls = forecast_url, stations

    async def _fetch_periods(self, client: httpx.AsyncClient) -> list[dict] | None:
        try:
            response = await client.get(self._forecast_url)
            response.raise_for_status()
            return parse_forecast(response.json())
        except Exception:
            log.warning("NWS forecast fetch failed", exc_info=True)
            return None

    async def _fetch_current(self, client: httpx.AsyncClient) -> dict | None:
        for station_url in self._station_urls:
            try:
                response = await client.get(f"{station_url}/observations/latest")
                response.raise_for_status()
                current = parse_observation(response.json())
            except Exception:
                log.warning("NWS observation fetch failed for %s", station_url, exc_info=True)
                continue
            if current is not None:
                return current
        return None


# Process-wide instance behind /api/v1/weather (one cache per uvicorn worker).
service = WeatherService()
