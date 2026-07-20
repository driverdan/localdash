"""Offline tests for the CarCruiseFinder listing scraper (fixture HTML, no network)."""

import datetime as dt
from pathlib import Path

import httpx
import pytest

from app.events.sources.carcruisefinder import (
    BROWSER_UA,
    LISTING_URL,
    CarCruiseFinderSource,
    parse_listing,
)

FIXTURES = Path(__file__).parent / "fixtures" / "carcruisefinder"
UTC = dt.timezone.utc


def load(name: str) -> str:
    return (FIXTURES / name).read_text()


def test_parse_listing_extracts_all_events():
    events = parse_listing(load("listing.html"))

    assert len(events) == 19
    assert all(e.source_name == "CarCruiseFinder" for e in events)
    assert all(e.start_time.tzinfo is not None for e in events)
    # RawEvent has no coordinate fields at all; assert the geo block wasn't
    # smuggled into any text field.
    for e in events:
        for value in (e.title, e.description, e.venue_name or "", e.address or ""):
            assert "35.11" not in value


def test_parse_listing_maps_jsonld_fields():
    events = parse_listing(load("listing.html"))
    (sonic,) = [
        e
        for e in events
        if e.source_event_id == "car-show/scenic-city-street-machines-cruise-in/2026-08-13"
    ]

    assert sonic.title == "Scenic City Street Machines Cruise in"
    # 2026-08-13T18:00:00-04:00 (EDT, correct DST offset) -> 22:00 UTC.
    assert sonic.start_time == dt.datetime(2026, 8, 13, 22, 0, tzinfo=UTC)
    assert sonic.end_time == dt.datetime(2026, 8, 14, 0, 0, tzinfo=UTC)
    assert sonic.venue_name == "Sonic"
    assert sonic.address == "3508 Dayton Blvd., Chattanooga, TN, United States"
    assert (
        sonic.source_url
        == "https://carcruisefinder.com/car-show/scenic-city-street-machines-cruise-in/2026-08-13/"
    )
    assert "cruise-in" in sonic.description


def test_parse_listing_maps_jsonld_image():
    events = parse_listing(load("listing.html"))
    (sonic,) = [
        e
        for e in events
        if e.source_event_id == "car-show/scenic-city-street-machines-cruise-in/2026-08-13"
    ]
    assert sonic.image_url is not None
    assert sonic.image_url.startswith("https://carcruisefinder.com/")


def test_image_accepts_string_list_and_object_forms():
    def one(image_json: str) -> object:
        html = f"""
        <script type="application/ld+json">
        {{"@type": "Event", "name": "M", "startDate": "2026-01-10T18:00:00",
          "url": "https://carcruisefinder.com/car-show/m/", "image": {image_json}}}
        </script>
        """
        (event,) = parse_listing(html)
        return event.image_url

    assert one('"https://ccf.test/a.jpg"') == "https://ccf.test/a.jpg"
    assert one('["https://ccf.test/a.jpg", "https://ccf.test/b.jpg"]') == "https://ccf.test/a.jpg"
    assert one('{"url": "https://ccf.test/a.jpg"}') == "https://ccf.test/a.jpg"
    assert one('"https://ccf.test/Generic-Car-Show.jpg"') is None


def test_no_jsonld_yields_zero_events():
    assert parse_listing(load("listing_no_jsonld.html")) == []


def test_undated_event_is_skipped_others_kept():
    events = parse_listing(load("listing_undated_event.html"))
    assert len(events) == 18  # 19 in the fixture, one stripped of startDate


def test_naive_start_date_is_interpreted_as_eastern():
    html = """
    <script type="application/ld+json">
    {"@type": "Event", "name": "Naive Meet", "startDate": "2026-01-10T18:00:00",
     "url": "https://carcruisefinder.com/car-show/naive-meet/"}
    </script>
    """
    (event,) = parse_listing(html)
    # January is EST (-05:00) -> 23:00 UTC.
    assert event.start_time == dt.datetime(2026, 1, 10, 23, 0, tzinfo=UTC)
    assert event.end_time is None


def install_transport(monkeypatch, handler):
    """Route the source's httpx client through a mock transport."""
    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def fake_client(**kwargs):
        kwargs["transport"] = transport
        return real_client(**kwargs)

    monkeypatch.setattr("app.events.sources.carcruisefinder.httpx.AsyncClient", fake_client)


async def test_fetch_sends_browser_ua_and_makes_one_request(monkeypatch):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, text=load("listing.html"))

    install_transport(monkeypatch, handler)
    events = await CarCruiseFinderSource().fetch()

    assert len(events) == 19
    assert len(requests) == 1
    assert str(requests[0].url) == LISTING_URL
    assert requests[0].headers["User-Agent"] == BROWSER_UA


async def test_fetch_http_error_raises(monkeypatch):
    install_transport(monkeypatch, lambda request: httpx.Response(403))

    with pytest.raises(httpx.HTTPStatusError):
        await CarCruiseFinderSource().fetch()


def test_build_sources_registers_carcruisefinder():
    from app.config import Settings
    from app.events.sources import build_sources

    sources = build_sources(Settings(_env_file=None))
    ccf = [s for s in sources if isinstance(s, CarCruiseFinderSource)]
    assert len(ccf) == 1
    # Default settings also register the Chattanooga Zoo scraper, the TN iCal
    # feed, the library tribe calendar, and the CitySpark calendar; no Meetup
    # without token.
    assert len(sources) == 5
