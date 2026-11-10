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
from datetime import datetime, timezone

import httpx

from app.config import Settings, get_settings
from app.http import make_client
from app.weather.airnow import airnow_error_messages, parse_airnow
from app.weather.nws import parse_forecast, parse_observation, parse_points, parse_stations
from app.weather.schemas import AirQuality, CurrentConditions, ForecastPeriod, WeatherPayload

log = logging.getLogger(__name__)

POINTS_URL = "https://api.weather.gov/points/{lat},{lon}"
# AirNow's current-observations-by-lat/lon-or-ZIP service (the replacement for
# /aq/observation/latLong/current/, retired 2026-10-01). It takes no radius: it
# always reports the closest reading per pollutant within a fixed 50 miles.
AIRNOW_URL = "https://www.airnowapi.org/aq/observation/current/ziplatlong/"
# Stations tried (nearest first) before giving up on current conditions.
STATION_LIMIT = 3


class WeatherService:
    def __init__(self, settings: Settings | None = None) -> None:
        # None: read the process settings on each get_current() (the module
        # singleton below), so constructing it reads nothing at import time.
        self._settings = settings
        self._lock = asyncio.Lock()
        self._payload: WeatherPayload | None = None
        self._fetched_at: float = 0.0
        # Per-process discovery result; None until the first successful /points hop.
        self._forecast_url: str | None = None
        self._station_urls: list[str] = []

    async def get_current(self, *, force: bool = False) -> WeatherPayload:
        """The shaped weather payload — cached, refreshed at most once per TTL.

        `force` skips only the TTL check (the scheduled job uses it: its ticks land
        one interval after the previous fetch *finished*, so the cache always looks
        marginally fresh and every other tick would otherwise be a cache hit).
        Locking, stale-on-failure, and AQI carry-forward still apply.
        """
        settings = self._settings or get_settings()
        ttl = settings.weather_cache_minutes * 60
        async with self._lock:
            fresh = time.monotonic() - self._fetched_at < ttl
            if self._payload is not None and fresh and not force:
                return self._payload
            try:
                payload = await self._refresh(settings)
            except Exception:
                if self._payload is None:
                    raise
                log.warning("weather refresh failed; serving stale payload", exc_info=True)
                return self._payload
            payload = self._carry_forward_aqi(payload, settings)
            self._payload = payload
            self._fetched_at = time.monotonic()
            return payload

    def _carry_forward_aqi(self, payload: WeatherPayload, settings: Settings) -> WeatherPayload:
        """Preserve the last-good AQI when a refresh produced none.

        A partial (AirNow-only) refresh failure yields aqi=None but succeeds
        overall, so without this the good prior AQI would be discarded for a
        full TTL — the intermittent-AQI bug. Carry the prior AQI forward while
        its observation is within airnow_stale_minutes; past that it drops to
        null so a dead feed does not linger indefinitely.
        """
        if payload.aqi is not None:
            return payload
        prior = self._payload
        if prior is None or prior.aqi is None:
            return payload
        if not self._aqi_within_max_age(prior.aqi, settings):
            return payload
        return payload.model_copy(update={"aqi": prior.aqi})

    def _aqi_within_max_age(self, aqi: AirQuality, settings: Settings) -> bool:
        max_age = settings.airnow_stale_minutes * 60
        observed = aqi.observed_at
        if observed:
            try:
                ts = datetime.fromisoformat(observed)
            except ValueError:
                ts = None
            # tz-aware observation time is the real bound; a naive one (unknown
            # AirNow zone) is display-only, so fall through to the fetch-age bound.
            if ts is not None and ts.tzinfo is not None:
                age = (datetime.now(timezone.utc) - ts).total_seconds()
                return age <= max_age
        # No usable observation time: bound by how long the prior payload (which
        # carried this AQI) has been cached. _fetched_at still holds its time here.
        return time.monotonic() - self._fetched_at <= max_age

    def _make_client(self, settings: Settings) -> httpx.AsyncClient:
        # NWS asks for an identifying User-Agent; geo+json is its native shape.
        return make_client(
            timeout=10.0,
            user_agent=settings.user_agent,
            follow_redirects=True,
            headers={"Accept": "application/geo+json"},
        )

    async def _refresh(self, settings: Settings) -> WeatherPayload:
        async with self._make_client(settings) as client:
            if self._forecast_url is None or not self._station_urls:
                await self._discover(client, settings)
            periods, current, aqi = await asyncio.gather(
                self._fetch_periods(client),
                self._fetch_current(client),
                self._fetch_aqi(client, settings),
            )
        # The halves fail independently. AQI is additive: only a refresh with
        # both NWS halves empty is an error, whether or not AirNow succeeded.
        if periods is None and current is None:
            raise RuntimeError("both NWS fetches failed")
        return WeatherPayload(current=current, periods=periods or [], aqi=aqi)

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

    async def _fetch_periods(self, client: httpx.AsyncClient) -> list[ForecastPeriod] | None:
        try:
            response = await client.get(self._forecast_url)
            response.raise_for_status()
            return parse_forecast(response.json())
        except Exception:
            log.warning("NWS forecast fetch failed", exc_info=True)
            return None

    async def _fetch_aqi(self, client: httpx.AsyncClient, settings: Settings) -> AirQuality | None:
        # The key doubles as the feature switch: empty means no request at all.
        if not settings.airnow_api_key:
            return None
        try:
            response = await client.get(
                AIRNOW_URL,
                params={
                    "format": "application/json",
                    "latitude": settings.center_lat,
                    "longitude": settings.center_lon,
                    "API_KEY": settings.airnow_api_key,
                },
            )
        except Exception:
            log.warning("AirNow AQI fetch failed", exc_info=True)
            return None
        # AirNow explains failures in a WebServiceError envelope (a retired
        # service, a bad key, or — with a 200 — no monitor data). Log its
        # messages rather than a bare status: they come from the body, so they
        # cannot carry the API_KEY query param.
        if response.is_error:
            messages = _airnow_messages(response)
            detail = f": {'; '.join(messages)}" if messages else ""
            log.warning("AirNow AQI fetch failed: HTTP %d%s", response.status_code, detail)
            return None
        try:
            payload = response.json()
        except Exception:
            log.warning("AirNow AQI fetch failed", exc_info=True)
            return None
        messages = airnow_error_messages(payload)
        if messages:
            log.warning("AirNow returned no observations: %s", "; ".join(messages))
            return None
        aqi = parse_airnow(payload)
        if aqi is None:
            log.warning("AirNow returned no usable observations")
        return aqi

    async def _fetch_current(self, client: httpx.AsyncClient) -> CurrentConditions | None:
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


def _airnow_messages(response: httpx.Response) -> list[str]:
    """Best-effort WebServiceError messages from an AirNow error response."""
    try:
        return airnow_error_messages(response.json())
    except ValueError:
        return []
