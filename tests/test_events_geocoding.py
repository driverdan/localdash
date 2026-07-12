"""Offline tests for NominatimGeocoder's request throttle."""
import asyncio
import time

import httpx

from app.events.geocoding import NominatimGeocoder

RESULT = [{"lat": "35.0456", "lon": "-85.3097"}]

# Scheduling jitter allowance: a send can land slightly early relative to the
# previous send's own jitter, never relative to its reserved slot.
TOLERANCE = 0.02


def install_transport(monkeypatch, send_times):
    """Route the geocoder's httpx client through a transport that records send times."""

    def handler(request: httpx.Request) -> httpx.Response:
        send_times.append(time.monotonic())
        return httpx.Response(200, json=RESULT)

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def fake_client(**kwargs):
        kwargs["transport"] = transport
        return real_client(**kwargs)

    monkeypatch.setattr("app.events.geocoding.httpx.AsyncClient", fake_client)


async def test_sequential_requests_are_spaced(monkeypatch):
    send_times: list[float] = []
    install_transport(monkeypatch, send_times)
    geocoder = NominatimGeocoder(user_agent="test", min_interval=0.05)

    for _ in range(3):
        assert await geocoder.geocode("1800 Rossville Ave") == (35.0456, -85.3097)

    assert len(send_times) == 3
    for earlier, later in zip(send_times, send_times[1:]):
        assert later - earlier >= 0.05 - TOLERANCE


async def test_concurrent_requests_are_spaced(monkeypatch):
    send_times: list[float] = []
    install_transport(monkeypatch, send_times)
    geocoder = NominatimGeocoder(user_agent="test", min_interval=0.05)

    results = await asyncio.gather(*(geocoder.geocode(f"addr {i}") for i in range(3)))

    assert all(r == (35.0456, -85.3097) for r in results)
    assert len(send_times) == 3
    ordered = sorted(send_times)
    for earlier, later in zip(ordered, ordered[1:]):
        assert later - earlier >= 0.05 - TOLERANCE


async def test_zero_interval_disables_throttle(monkeypatch):
    send_times: list[float] = []
    install_transport(monkeypatch, send_times)
    geocoder = NominatimGeocoder(user_agent="test", min_interval=0)

    start = time.monotonic()
    for _ in range(3):
        await geocoder.geocode("1800 Rossville Ave")

    assert len(send_times) == 3
    # Three mocked round-trips with no throttle finish near-instantly; well
    # under a single 1s policy interval even on a slow CI box.
    assert time.monotonic() - start < 0.5


async def test_empty_address_skips_throttle_and_request(monkeypatch):
    send_times: list[float] = []
    install_transport(monkeypatch, send_times)
    # min_interval high enough that consuming a slot would visibly delay the
    # real request that follows.
    geocoder = NominatimGeocoder(user_agent="test", min_interval=10)

    start = time.monotonic()
    assert await geocoder.geocode("") is None
    assert await geocoder.geocode("1800 Rossville Ave") == (35.0456, -85.3097)

    assert len(send_times) == 1
    assert time.monotonic() - start < 1.0
