"""Offline tests for The Events Calendar (tribe) REST source.

The fixture is a trimmed real capture of the Chattanooga Public Library's
``/wp-json/tribe/events/v1/events`` page (three real events, including two
occurrences of one recurring series) plus two synthetic events: an
entity-titled/HTML-described event whose venue has an address but no geo, and
a broken event without ``utc_start_date`` whose venue is the API's absent-form
``[]``.
"""

import datetime as dt
import json
from pathlib import Path

import httpx

from app.config import Settings
from app.events.sources import build_sources
from app.events.sources.tribe import MAX_PAGES, PAGE_SIZE, TribeEventsSource, parse_page

FIXTURE = Path(__file__).parent / "fixtures" / "tribe" / "events_page.json"
UTC = dt.timezone.utc
SOURCE_NAME = "Chattanooga Public Library"


def load_page() -> dict:
    return json.loads(FIXTURE.read_text())


def make_event(**overrides) -> dict:
    base = {
        "id": 1,
        "title": "Test Event",
        "description": "",
        "url": "https://example.org/event/test/",
        "utc_start_date": "2026-07-20 14:00:00",
        "image": False,
        "categories": [],
        "venue": [],
    }
    base.update(overrides)
    return base


def make_page(events: list[dict], total_pages: int = 1) -> dict:
    return {"events": events, "total": len(events), "total_pages": total_pages}


# --- parse: fixture ---


def test_parse_page_extracts_dated_fixture_events():
    events = parse_page(load_page(), SOURCE_NAME)

    assert len(events) == 4  # 5 fixture events minus the one without a UTC start
    assert all(e.source_name == SOURCE_NAME for e in events)
    assert all(e.start_time.tzinfo is not None for e in events)
    assert all(e.source_event_id for e in events)


def test_parse_page_maps_fields():
    events = parse_page(load_page(), SOURCE_NAME)
    baby_bounce = next(e for e in events if e.source_event_id == "10047982")

    assert baby_bounce.title == "Baby Bounce Downtown (Ages 0-18 Months)"
    assert baby_bounce.start_time == dt.datetime(2026, 7, 20, 14, 0, tzinfo=UTC)
    assert baby_bounce.end_time == dt.datetime(2026, 7, 20, 14, 30, tzinfo=UTC)
    assert baby_bounce.venue_name == "Downtown Library"
    assert baby_bounce.address == "1001 Broad Street, Chattanooga, TN, 37402"
    assert (baby_bounce.latitude, baby_bounce.longitude) == (35.0443426, -85.3108154)
    assert baby_bounce.image_url == (
        "https://chattlibrary.org/wp-content/uploads/2025/05/Baby-Bounce-updated.png"
    )
    assert baby_bounce.tags == ["babies", "infants", "literacy", "parents", "reading"]
    assert "sing and play" in baby_bounce.description
    assert "<p>" not in baby_bounce.description


def test_recurring_occurrences_stay_distinct():
    events = parse_page(load_page(), SOURCE_NAME)
    series = [e for e in events if "nd-saturday-10am-2" in e.source_url]

    assert len(series) == 2
    first, second = series
    assert first.title == second.title
    assert first.source_event_id != second.source_event_id
    assert first.source_url != second.source_url  # occurrence-dated event pages
    assert first.start_time != second.start_time


def test_venue_without_geo_keeps_address_for_the_geocoder():
    events = parse_page(load_page(), SOURCE_NAME)
    talk = next(e for e in events if e.source_event_id == "9999001")

    assert talk.latitude is None and talk.longitude is None
    assert talk.address == "925 W 39th St, Chattanooga, TN, 37409"
    assert talk.venue_name == "South Chattanooga Library"


def test_html_is_reduced_to_text():
    events = parse_page(load_page(), SOURCE_NAME)
    talk = next(e for e in events if e.source_event_id == "9999001")

    assert talk.title == 'Author Talk – Judith Garrison’s "See Rock City Barns"'
    assert talk.description == "Meet the author & hear the story."


def test_event_without_utc_start_is_skipped_and_parse_continues(caplog):
    with caplog.at_level("WARNING", logger="localdash.events"):
        events = parse_page(load_page(), SOURCE_NAME)

    assert "9999002" not in [e.source_event_id for e in events]
    assert "utc_start_date" in caplog.text


# --- parse: synthetic edges ---


def test_absent_subobjects_yield_no_image_venue_or_tags():
    (event,) = parse_page(make_page([make_event()]), SOURCE_NAME)

    assert event.image_url is None
    assert event.venue_name is None and event.address is None
    assert event.latitude is None and event.longitude is None
    assert event.tags == []


def test_placeholder_image_is_excluded():
    (event,) = parse_page(
        make_page([make_event(image={"url": "https://blob.test/Generic-Event.jpg"})]),
        SOURCE_NAME,
    )
    assert event.image_url is None


def test_empty_title_falls_back_to_untitled():
    (event,) = parse_page(make_page([make_event(title="")]), SOURCE_NAME)
    assert event.title == "Untitled event"


def test_false_venue_geo_is_treated_as_absent():
    venue = {"venue": "Somewhere", "geo_lat": False, "geo_lng": False}
    (event,) = parse_page(make_page([make_event(venue=venue)]), SOURCE_NAME)
    assert event.latitude is None and event.longitude is None


# --- fetch: pagination ---


def make_source(**overrides) -> TribeEventsSource:
    kwargs = dict(base_url="https://example.org", name=SOURCE_NAME, lookahead_days=14)
    kwargs.update(overrides)
    return TribeEventsSource(**kwargs)


def install_transport(monkeypatch, handler):
    """Route the source's httpx client through a mock transport."""
    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def fake_client(**kwargs):
        kwargs["transport"] = transport
        return real_client(**kwargs)

    monkeypatch.setattr("app.events.sources.tribe.httpx.AsyncClient", fake_client)


def paged_handler(pages: list[list[dict]], requests: list[httpx.Request]):
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        page = int(request.url.params.get("page"))
        events = pages[page - 1] if page <= len(pages) else []
        return httpx.Response(200, json=make_page(events, total_pages=len(pages)))

    return handler


async def test_fetch_follows_total_pages_within_the_date_window(monkeypatch):
    pages = [
        [make_event(id=i, title=f"Event {i}") for i in range(PAGE_SIZE)],
        [make_event(id=PAGE_SIZE, title=f"Event {PAGE_SIZE}")],
    ]
    requests: list[httpx.Request] = []
    install_transport(monkeypatch, paged_handler(pages, requests))

    events = await make_source().fetch()

    assert len(events) == PAGE_SIZE + 1
    assert [int(r.url.params["page"]) for r in requests] == [1, 2]
    first = requests[0]
    assert first.url.path == "/wp-json/tribe/events/v1/events"
    assert int(first.url.params["per_page"]) == PAGE_SIZE
    start = dt.date.fromisoformat(first.url.params["start_date"])
    end = dt.date.fromisoformat(first.url.params["end_date"])
    assert (end - start).days == 14


async def test_fetch_page_cap_bounds_a_non_terminating_loop(monkeypatch):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=make_page([make_event()], total_pages=999))

    install_transport(monkeypatch, handler)

    await make_source().fetch()

    assert len(requests) == MAX_PAGES


# --- build_sources: configuration ---


def test_build_sources_registers_the_library_calendar_by_default():
    sources = build_sources(Settings(_env_file=None))
    (tribe,) = [s for s in sources if isinstance(s, TribeEventsSource)]

    assert tribe.name == "Chattanooga Public Library"
    assert tribe.base_url == "https://chattlibrary.org"
    assert tribe.lookahead_days == 14


def test_build_sources_override_replaces_the_default():
    sources = build_sources(
        Settings(
            _env_file=None,
            events_tribe_calendars="Venue A=https://a.example, Venue B=https://b.example/",
        )
    )
    tribes = [s for s in sources if isinstance(s, TribeEventsSource)]

    assert [(t.name, t.base_url) for t in tribes] == [
        ("Venue A", "https://a.example"),
        ("Venue B", "https://b.example"),
    ]


def test_build_sources_empty_setting_disables_tribe_ingestion():
    sources = build_sources(Settings(_env_file=None, events_tribe_calendars=""))
    assert not [s for s in sources if isinstance(s, TribeEventsSource)]


def test_build_sources_skips_malformed_entries_loudly(caplog):
    with caplog.at_level("WARNING", logger="localdash.events"):
        sources = build_sources(
            Settings(
                _env_file=None,
                events_tribe_calendars="https://no-name.example, Venue A=https://a.example",
            )
        )
    tribes = [s for s in sources if isinstance(s, TribeEventsSource)]

    assert [t.name for t in tribes] == ["Venue A"]
    assert "events_tribe_calendars" in caplog.text
