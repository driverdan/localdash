"""Offline tests for the weather feature (no network, no DB).

Shaping functions are exercised against recorded NWS fixture payloads; the
fetch/cache layer runs against an httpx.MockTransport standing in for
api.weather.gov.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from app.config import get_settings
from app.weather.airnow import parse_airnow
from app.weather.nws import parse_forecast, parse_observation, parse_points, parse_stations
from app.weather.service import AIRNOW_URL, STATION_LIMIT, WeatherService

FIXTURES = Path(__file__).parent / "fixtures" / "nws"
AIRNOW_FIXTURES = Path(__file__).parent / "fixtures" / "airnow"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text())


def _load_airnow(name: str) -> list:
    return json.loads((AIRNOW_FIXTURES / f"{name}.json").read_text())


@pytest.fixture(autouse=True)
def _pin_airnow_key(monkeypatch):
    """Pin AIRNOW_API_KEY empty so a developer .env key can't leak AirNow
    fetches into the NWS tests; AQI tests opt in via _set_airnow_key."""
    monkeypatch.setenv("AIRNOW_API_KEY", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _set_airnow_key(monkeypatch, key: str = "test-key") -> None:
    monkeypatch.setenv("AIRNOW_API_KEY", key)
    get_settings.cache_clear()


# --- pure shaping ---


def test_parse_points_yields_forecast_and_stations_urls():
    forecast_url, stations_url = parse_points(_load("points"))
    assert forecast_url == "https://api.weather.gov/gridpoints/MRX/57,51/forecast"
    assert stations_url == "https://api.weather.gov/gridpoints/MRX/57,51/stations"


def test_parse_stations_keeps_nearest_first_up_to_limit():
    stations = parse_stations(_load("stations"), STATION_LIMIT)
    assert stations == [
        "https://api.weather.gov/stations/KCHA",
        "https://api.weather.gov/stations/KDNT",
        "https://api.weather.gov/stations/KCQN",
    ]


def test_parse_forecast_passes_period_names_through():
    periods = parse_forecast(_load("forecast"))
    assert [p["name"] for p in periods] == ["Today", "Tonight"]  # verbatim, first two only
    today = periods[0]
    assert today["temperature"] == 92
    assert today["temperature_unit"] == "F"
    assert today["precip_percent"] == 20
    assert today["short_forecast"] == "Mostly Sunny"
    assert "high near 92" in today["detailed_forecast"]
    assert periods[1]["precip_percent"] is None  # null probability stays null


def test_parse_observation_converts_units():
    current = parse_observation(_load("observation"))
    assert current["temperature_f"] == 89  # 31.7 °C
    assert current["description"] == "Partly Cloudy"
    assert current["icon"].startswith("https://api.weather.gov/icons/")
    assert current["wind_mph"] == 6  # 9.36 km/h
    assert current["wind_direction"] == "SW"  # 230°
    assert current["humidity_percent"] == 58
    assert current["observed_at"] == "2026-07-16T14:53:00+00:00"


def test_parse_observation_null_temperature_is_unusable():
    assert parse_observation(_load("observation_null_temp")) is None


def test_parse_airnow_overall_aqi_is_the_worst_pollutant():
    aqi = parse_airnow(_load_airnow("current"))
    assert aqi == {
        "value": 62,
        "category": 2,
        "category_name": "Moderate",
        "pollutant": "PM2.5",
        # DateObserved 2026-07-16, HourObserved 14, LocalTimeZone EST -> UTC-5.
        "observed_at": "2026-07-16T14:00:00-05:00",
    }


def test_parse_airnow_unknown_timezone_yields_naive_observed_at():
    entries = _load_airnow("current")
    for entry in entries:
        entry["LocalTimeZone"] = "ZZZ"  # not in the offset table
    aqi = parse_airnow(entries)
    assert aqi["observed_at"] == "2026-07-16T14:00:00"  # naive, display-only


def test_parse_airnow_skips_sentinel_values():
    entries = _load_airnow("current")
    entries[1]["AQI"] = -999  # AirNow's missing-value sentinel on PM2.5
    aqi = parse_airnow(entries)
    assert aqi["pollutant"] == "O3" and aqi["value"] == 41


def test_parse_airnow_no_usable_entries_is_none():
    assert parse_airnow([]) is None
    assert parse_airnow([{"ParameterName": "O3", "AQI": -999}]) is None


# --- fetch/cache layer ---

POINTS = "https://api.weather.gov/points/35.0456,-85.3097"
STATIONS = "https://api.weather.gov/gridpoints/MRX/57,51/stations"
FORECAST = "https://api.weather.gov/gridpoints/MRX/57,51/forecast"
OBS_KCHA = "https://api.weather.gov/stations/KCHA/observations/latest"
OBS_KDNT = "https://api.weather.gov/stations/KDNT/observations/latest"


class FakeNWS:
    """MockTransport handler: fixture per URL, per-URL failure toggles, call log.

    Also stands in for airnowapi.org (same client, same transport). Routes are
    keyed query-free — AirNow's params vary per request — while the call log
    keeps full URLs so tests can assert on query contents.
    """

    def __init__(self) -> None:
        self.routes = {
            POINTS: _load("points"),
            STATIONS: _load("stations"),
            FORECAST: _load("forecast"),
            OBS_KCHA: _load("observation"),
        }
        self.failing: set[str] = set()
        self.calls: list[str] = []

    def service(self) -> WeatherService:
        svc = WeatherService()
        svc._transport = httpx.MockTransport(self.handle)
        return svc

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(str(request.url))
        assert request.headers["User-Agent"] == "LocalDash/0.1"  # NWS-required UA
        url = str(request.url.copy_with(query=None))
        if url in self.failing or url not in self.routes:
            return httpx.Response(500)
        return httpx.Response(200, json=self.routes[url])


async def test_refresh_shapes_full_payload():
    nws = FakeNWS()
    payload = await nws.service().get_current()
    assert payload["current"]["temperature_f"] == 89
    assert [p["name"] for p in payload["periods"]] == ["Today", "Tonight"]


async def test_second_request_within_ttl_hits_cache():
    nws = FakeNWS()
    svc = nws.service()
    first = await svc.get_current()
    calls_after_first = len(nws.calls)
    assert await svc.get_current() is first
    assert len(nws.calls) == calls_after_first  # no upstream traffic


async def test_discovery_happens_once_per_process():
    nws = FakeNWS()
    svc = nws.service()
    await svc.get_current()
    # Expire the TTL. -inf, not 0: time.monotonic() is seconds since boot on
    # Linux, so on a freshly booted machine (CI) 0 can still be within the TTL.
    svc._fetched_at = float("-inf")
    await svc.get_current()
    assert nws.calls.count(POINTS) == 1
    assert nws.calls.count(STATIONS) == 1
    assert nws.calls.count(FORECAST) == 2


async def test_failed_discovery_is_retried_next_request():
    nws = FakeNWS()
    svc = nws.service()
    nws.failing.add(POINTS)
    with pytest.raises(Exception):
        await svc.get_current()
    nws.failing.clear()
    payload = await svc.get_current()
    assert nws.calls.count(POINTS) == 2
    assert payload["current"] is not None


async def test_stale_payload_served_on_refresh_failure():
    nws = FakeNWS()
    svc = nws.service()
    fresh = await svc.get_current()
    # Expire the TTL. -inf, not 0: time.monotonic() is seconds since boot on
    # Linux, so on a freshly booted machine (CI) 0 can still be within the TTL.
    svc._fetched_at = float("-inf")
    nws.failing.update({FORECAST, OBS_KCHA, OBS_KDNT})
    nws.routes[OBS_KDNT] = {}  # ensure fallback also fails
    assert await svc.get_current() is fresh


async def test_cold_failure_raises():
    nws = FakeNWS()
    nws.failing.update({FORECAST, OBS_KCHA})
    with pytest.raises(RuntimeError):
        await nws.service().get_current()


async def test_partial_failure_yields_partial_payload():
    nws = FakeNWS()
    nws.failing.add(OBS_KCHA)  # every station fails -> no current conditions
    payload = await nws.service().get_current()
    assert payload["current"] is None
    assert [p["name"] for p in payload["periods"]] == ["Today", "Tonight"]


async def test_null_temperature_falls_back_to_next_station():
    nws = FakeNWS()
    nws.routes[OBS_KCHA] = _load("observation_null_temp")
    nws.routes[OBS_KDNT] = _load("observation")
    payload = await nws.service().get_current()
    assert payload["current"]["temperature_f"] == 89
    assert nws.calls.count(OBS_KCHA) == 1 and nws.calls.count(OBS_KDNT) == 1


# --- AirNow AQI ---


def _airnow_calls(nws: FakeNWS) -> list[str]:
    return [call for call in nws.calls if call.startswith(AIRNOW_URL)]


async def test_refresh_includes_aqi_when_configured(monkeypatch):
    _set_airnow_key(monkeypatch)
    nws = FakeNWS()
    nws.routes[AIRNOW_URL] = _load_airnow("current")
    payload = await nws.service().get_current()
    assert payload["aqi"]["value"] == 62 and payload["aqi"]["category"] == 2
    assert payload["current"]["temperature_f"] == 89  # NWS halves untouched
    assert "API_KEY=test-key" in _airnow_calls(nws)[0]  # key travels as a param


async def test_empty_key_makes_no_airnow_request():
    nws = FakeNWS()
    payload = await nws.service().get_current()
    assert payload["aqi"] is None
    assert _airnow_calls(nws) == []


async def test_airnow_failure_leaves_weather_intact(monkeypatch):
    _set_airnow_key(monkeypatch)
    nws = FakeNWS()  # no AirNow route -> 500, the error-status path
    payload = await nws.service().get_current()
    assert payload["aqi"] is None
    assert payload["current"]["temperature_f"] == 89
    assert [p["name"] for p in payload["periods"]] == ["Today", "Tonight"]


async def test_airnow_success_does_not_rescue_cold_failure(monkeypatch):
    _set_airnow_key(monkeypatch)
    nws = FakeNWS()
    nws.routes[AIRNOW_URL] = _load_airnow("current")
    nws.failing.update({FORECAST, OBS_KCHA})
    with pytest.raises(RuntimeError):
        await nws.service().get_current()


# --- last-good AQI carry-forward ---


def _airnow_at(minutes_ago: int) -> list:
    """`current` fixture stamped so its observation is ~`minutes_ago` old.

    AirNow reports hourly, so the parsed observed_at floors to the top of the
    hour — the reading ends up between `minutes_ago` and `minutes_ago`+59 old.
    Stamped in a known zone (EST) so parse_airnow yields a tz-aware timestamp.
    """
    entries = _load_airnow("current")
    ts = datetime.now(timezone(timedelta(hours=-5))) - timedelta(minutes=minutes_ago)
    for entry in entries:
        entry["DateObserved"] = ts.strftime("%Y-%m-%d")
        entry["HourObserved"] = ts.hour
        entry["LocalTimeZone"] = "EST"
    return entries


async def test_last_good_aqi_carried_forward_on_airnow_failure(monkeypatch):
    _set_airnow_key(monkeypatch)
    nws = FakeNWS()
    nws.routes[AIRNOW_URL] = _airnow_at(0)  # fresh, well within the max age
    svc = nws.service()
    first = await svc.get_current()
    good_aqi = first["aqi"]
    assert good_aqi["value"] == 62
    # Next refresh: TTL expired, AirNow now fails, NWS still succeeds.
    svc._fetched_at = float("-inf")
    del nws.routes[AIRNOW_URL]  # unrouted -> 500
    second = await svc.get_current()
    assert second["aqi"] == good_aqi  # carried forward verbatim, observed_at intact
    assert second["current"]["temperature_f"] == 89  # NWS half fresh


async def test_stale_aqi_dropped_past_max_age(monkeypatch):
    _set_airnow_key(monkeypatch)
    nws = FakeNWS()
    nws.routes[AIRNOW_URL] = _airnow_at(240)  # older than airnow_stale_minutes (120)
    svc = nws.service()
    first = await svc.get_current()
    assert first["aqi"]["value"] == 62  # shaping never age-checks; first fetch shows it
    svc._fetched_at = float("-inf")
    del nws.routes[AIRNOW_URL]
    second = await svc.get_current()
    assert second["aqi"] is None  # too old to carry forward
    assert second["current"]["temperature_f"] == 89
