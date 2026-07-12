"""Offline tests for NominatimGeocoder's request throttle and query fallbacks."""
import asyncio
import time

import httpx

from app.events.geocoding import NominatimGeocoder, _candidate_queries

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


# --- fallback query simplification ---

VENUE_ADDRESS = (
    "O'Charley's on Riverside, 674 N Riverside Drive, Clarksville, TN, 37040, United States"
)
STREET_ADDRESS = "674 N Riverside Drive, Clarksville, TN, 37040, United States"
LOCALITY_TAIL = "Clarksville, TN, 37040, United States"


def install_query_transport(monkeypatch, sent_queries, responder):
    """Route the geocoder through a transport that records each q= and answers via responder."""

    def handler(request: httpx.Request) -> httpx.Response:
        query = request.url.params["q"]
        sent_queries.append(query)
        return responder(query)

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def fake_client(**kwargs):
        kwargs["transport"] = transport
        return real_client(**kwargs)

    monkeypatch.setattr("app.events.geocoding.httpx.AsyncClient", fake_client)


def test_candidate_queries_shapes():
    assert _candidate_queries(VENUE_ADDRESS) == [VENUE_ADDRESS, STREET_ADDRESS, LOCALITY_TAIL]
    # Too few components to strip anything.
    assert _candidate_queries("1800 Rossville Ave, Chattanooga, TN") == [
        "1800 Rossville Ave, Chattanooga, TN"
    ]
    # Five components: the stripped variant IS the locality tail — deduplicated.
    five = "674 N Riverside Drive, Clarksville, TN, 37040, United States"
    assert _candidate_queries(five) == [five, "Clarksville, TN, 37040, United States"]


async def test_venue_prefix_falls_back_to_street_address(monkeypatch):
    sent: list[str] = []
    install_query_transport(
        monkeypatch,
        sent,
        lambda q: httpx.Response(200, json=RESULT if q == STREET_ADDRESS else []),
    )
    geocoder = NominatimGeocoder(user_agent="test", min_interval=0)

    assert await geocoder.geocode(VENUE_ADDRESS) == (35.0456, -85.3097)
    assert sent == [VENUE_ADDRESS, STREET_ADDRESS]


async def test_double_fallback_to_locality_tail(monkeypatch):
    sent: list[str] = []
    install_query_transport(
        monkeypatch,
        sent,
        lambda q: httpx.Response(200, json=RESULT if q == LOCALITY_TAIL else []),
    )
    geocoder = NominatimGeocoder(user_agent="test", min_interval=0)

    assert await geocoder.geocode(VENUE_ADDRESS) == (35.0456, -85.3097)
    assert sent == [VENUE_ADDRESS, STREET_ADDRESS, LOCALITY_TAIL]


async def test_all_candidates_fail_returns_none(monkeypatch):
    sent: list[str] = []
    install_query_transport(monkeypatch, sent, lambda q: httpx.Response(200, json=[]))
    geocoder = NominatimGeocoder(user_agent="test", min_interval=0)

    assert await geocoder.geocode(VENUE_ADDRESS) is None
    assert sent == [VENUE_ADDRESS, STREET_ADDRESS, LOCALITY_TAIL]


async def test_short_address_has_no_fallbacks(monkeypatch):
    sent: list[str] = []
    install_query_transport(monkeypatch, sent, lambda q: httpx.Response(200, json=[]))
    geocoder = NominatimGeocoder(user_agent="test", min_interval=0)

    assert await geocoder.geocode("1800 Rossville Ave, Chattanooga, TN") is None
    assert sent == ["1800 Rossville Ave, Chattanooga, TN"]


async def test_service_error_stops_fallback_chain(monkeypatch):
    sent: list[str] = []
    install_query_transport(monkeypatch, sent, lambda q: httpx.Response(503))
    geocoder = NominatimGeocoder(user_agent="test", min_interval=0)

    assert await geocoder.geocode(VENUE_ADDRESS) is None
    assert sent == [VENUE_ADDRESS]


async def test_fallback_attempts_are_rate_limited(monkeypatch):
    send_times: list[float] = []
    install_query_transport(
        monkeypatch,
        sent_queries=[],
        responder=lambda q: (send_times.append(time.monotonic()), httpx.Response(200, json=[]))[1],
    )
    geocoder = NominatimGeocoder(user_agent="test", min_interval=0.05)

    assert await geocoder.geocode(VENUE_ADDRESS) is None
    assert len(send_times) == 3
    for earlier, later in zip(send_times, send_times[1:]):
        assert later - earlier >= 0.05 - TOLERANCE
