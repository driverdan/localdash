"""Offline tests for NominatimGeocoder's request throttle, query fallbacks and client lifetime."""

import asyncio
import time

import httpx
import pytest

import app.events.geocoding as geocoding_mod
from app.events.geocoding import NominatimGeocoder, _candidate_queries

RESULT = [{"lat": "35.0456", "lon": "-85.3097"}]

# Scheduling jitter allowance: a send can land slightly early relative to the
# previous send's own jitter, never relative to its reserved slot.
TOLERANCE = 0.02


def timing_handler(send_times):
    """A mock_http handler that records each send time and answers with RESULT."""

    def handler(request: httpx.Request) -> httpx.Response:
        send_times.append(time.monotonic())
        return httpx.Response(200, json=RESULT)

    return handler


async def test_sequential_requests_are_spaced(mock_http):
    send_times: list[float] = []
    mock_http.install(timing_handler(send_times))

    async with NominatimGeocoder(user_agent="test", min_interval=0.05) as geocoder:
        for _ in range(3):
            assert await geocoder.geocode("1800 Rossville Ave") == (35.0456, -85.3097)

    assert len(send_times) == 3
    for earlier, later in zip(send_times, send_times[1:]):
        assert later - earlier >= 0.05 - TOLERANCE


async def test_concurrent_requests_are_spaced(mock_http):
    send_times: list[float] = []
    mock_http.install(timing_handler(send_times))

    async with NominatimGeocoder(user_agent="test", min_interval=0.05) as geocoder:
        results = await asyncio.gather(*(geocoder.geocode(f"addr {i}") for i in range(3)))

    assert all(r == (35.0456, -85.3097) for r in results)
    assert len(send_times) == 3
    ordered = sorted(send_times)
    for earlier, later in zip(ordered, ordered[1:]):
        assert later - earlier >= 0.05 - TOLERANCE


async def test_zero_interval_disables_throttle(mock_http):
    send_times: list[float] = []
    mock_http.install(timing_handler(send_times))

    start = time.monotonic()
    async with NominatimGeocoder(user_agent="test", min_interval=0) as geocoder:
        for _ in range(3):
            await geocoder.geocode("1800 Rossville Ave")

    assert len(send_times) == 3
    # Three mocked round-trips with no throttle finish near-instantly; well
    # under a single 1s policy interval even on a slow CI box.
    assert time.monotonic() - start < 0.5


async def test_empty_address_skips_throttle_and_request(mock_http):
    send_times: list[float] = []
    mock_http.install(timing_handler(send_times))

    start = time.monotonic()
    # min_interval high enough that consuming a slot would visibly delay the
    # real request that follows.
    async with NominatimGeocoder(user_agent="test", min_interval=10) as geocoder:
        assert await geocoder.geocode("") is None
        assert await geocoder.geocode("1800 Rossville Ave") == (35.0456, -85.3097)

    assert len(send_times) == 1
    assert time.monotonic() - start < 1.0


# --- client lifetime ---


async def test_one_client_serves_every_lookup_and_closes_on_exit(monkeypatch, mock_http):
    mock_http.install(lambda request: httpx.Response(200, json=RESULT))
    clients: list[httpx.AsyncClient] = []
    real_make_client = geocoding_mod.make_client

    def spy(**kwargs):
        client = real_make_client(**kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr(geocoding_mod, "make_client", spy)

    async with NominatimGeocoder(user_agent="test", min_interval=0) as geocoder:
        for i in range(3):
            await geocoder.geocode(f"addr {i}")
        assert len(clients) == 1
        assert not clients[0].is_closed

    assert len(mock_http.requests) == 3
    assert len(clients) == 1
    assert clients[0].is_closed


async def test_geocode_outside_the_context_raises_without_sending(mock_http):
    mock_http.install(lambda request: httpx.Response(200, json=RESULT))
    geocoder = NominatimGeocoder(user_agent="test", min_interval=0)

    with pytest.raises(RuntimeError):
        await geocoder.geocode("1800 Rossville Ave")

    async with geocoder:
        pass
    with pytest.raises(RuntimeError):  # and again once the context has closed
        await geocoder.geocode("1800 Rossville Ave")

    assert mock_http.requests == []


async def test_request_line_and_headers(mock_http):
    mock_http.install(lambda request: httpx.Response(200, json=RESULT))

    async with NominatimGeocoder(user_agent="LocalDash-test/1.0 (x@example.com)") as geocoder:
        await geocoder.geocode("1800 Rossville Ave")

    (request,) = mock_http.requests
    assert request.method == "GET"
    assert request.url.copy_with(query=None) == "https://nominatim.openstreetmap.org/search"
    assert dict(request.url.params) == {"q": "1800 Rossville Ave", "format": "json", "limit": "1"}
    assert request.headers["User-Agent"] == "LocalDash-test/1.0 (x@example.com)"


# --- fallback query simplification ---

VENUE_ADDRESS = (
    "O'Charley's on Riverside, 674 N Riverside Drive, Clarksville, TN, 37040, United States"
)
STREET_ADDRESS = "674 N Riverside Drive, Clarksville, TN, 37040, United States"
LOCALITY_TAIL = "Clarksville, TN, 37040, United States"


def query_handler(sent_queries, responder):
    """A mock_http handler that records each q= and answers via responder."""

    def handler(request: httpx.Request) -> httpx.Response:
        query = request.url.params["q"]
        sent_queries.append(query)
        return responder(query)

    return handler


async def geocode_once(address: str, min_interval: float = 0):
    async with NominatimGeocoder(user_agent="test", min_interval=min_interval) as geocoder:
        return await geocoder.geocode(address)


def test_candidate_queries_shapes():
    assert _candidate_queries(VENUE_ADDRESS) == [VENUE_ADDRESS, STREET_ADDRESS, LOCALITY_TAIL]
    # Too few components to strip anything.
    assert _candidate_queries("1800 Rossville Ave, Chattanooga, TN") == [
        "1800 Rossville Ave, Chattanooga, TN"
    ]
    # Five components: the stripped variant IS the locality tail — deduplicated.
    five = "674 N Riverside Drive, Clarksville, TN, 37040, United States"
    assert _candidate_queries(five) == [five, "Clarksville, TN, 37040, United States"]


async def test_venue_prefix_falls_back_to_street_address(mock_http):
    sent: list[str] = []
    mock_http.install(
        query_handler(
            sent, lambda q: httpx.Response(200, json=RESULT if q == STREET_ADDRESS else [])
        )
    )

    assert await geocode_once(VENUE_ADDRESS) == (35.0456, -85.3097)
    assert sent == [VENUE_ADDRESS, STREET_ADDRESS]


async def test_double_fallback_to_locality_tail(mock_http):
    sent: list[str] = []
    mock_http.install(
        query_handler(
            sent, lambda q: httpx.Response(200, json=RESULT if q == LOCALITY_TAIL else [])
        )
    )

    assert await geocode_once(VENUE_ADDRESS) == (35.0456, -85.3097)
    assert sent == [VENUE_ADDRESS, STREET_ADDRESS, LOCALITY_TAIL]


async def test_all_candidates_fail_returns_none(mock_http):
    sent: list[str] = []
    mock_http.install(query_handler(sent, lambda q: httpx.Response(200, json=[])))

    assert await geocode_once(VENUE_ADDRESS) is None
    assert sent == [VENUE_ADDRESS, STREET_ADDRESS, LOCALITY_TAIL]


async def test_short_address_has_no_fallbacks(mock_http):
    sent: list[str] = []
    mock_http.install(query_handler(sent, lambda q: httpx.Response(200, json=[])))

    assert await geocode_once("1800 Rossville Ave, Chattanooga, TN") is None
    assert sent == ["1800 Rossville Ave, Chattanooga, TN"]


async def test_service_error_stops_fallback_chain(mock_http):
    sent: list[str] = []
    mock_http.install(query_handler(sent, lambda q: httpx.Response(503)))

    assert await geocode_once(VENUE_ADDRESS) is None
    assert sent == [VENUE_ADDRESS]


async def test_fallback_attempts_are_rate_limited(mock_http):
    send_times: list[float] = []
    mock_http.install(
        query_handler(
            [],
            lambda q: (send_times.append(time.monotonic()), httpx.Response(200, json=[]))[1],
        )
    )

    assert await geocode_once(VENUE_ADDRESS, min_interval=0.05) is None
    assert len(send_times) == 3
    for earlier, later in zip(send_times, send_times[1:]):
        assert later - earlier >= 0.05 - TOLERANCE
