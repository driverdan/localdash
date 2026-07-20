"""Offline tests for the Chattanooga Zoo scraper (fixture HTML, no network)."""

import datetime as dt
from pathlib import Path

import httpx
import pytest

from app.events.sources.chattzoo import (
    LISTING_URL,
    SOURCE_NAME,
    VENUE_LAT,
    VENUE_LON,
    ChattZooSource,
    ListingEntry,
    parse_detail,
    parse_listing,
    resolve_year,
)

FIXTURES = Path(__file__).parent / "fixtures" / "chattzoo"
UTC = dt.timezone.utc

# The fixtures were captured in July 2026; tests pin "now" so year resolution
# is deterministic rather than drifting with the wall clock.
NOW = dt.datetime(2026, 7, 20, 12, 0, tzinfo=UTC)


def load(name: str) -> str:
    return (FIXTURES / name).read_text()


def entry_for(
    name: str = "Adventure Days", url: str = "https://www.chattzoo.org/events/x"
) -> ListingEntry:
    return ListingEntry(title=name, url=url, image_url="https://example.test/i.png")


# --- listing ---------------------------------------------------------------


def test_parse_listing_extracts_cards():
    entries = parse_listing(load("listing.html"))

    assert [e.url for e in entries] == [
        "https://www.chattzoo.org/events/adventure-days",
        "https://www.chattzoo.org/events/pirates-parrots-princesses",
        "https://www.chattzoo.org/events/member-appreciation-back-to-school",
        "https://www.chattzoo.org/events/homeschool-days",
    ]
    assert entries[0].title == "Adventure Days"
    assert entries[0].image_url is not None
    assert entries[0].image_url.startswith("https://chazoo.s3.amazonaws.com/")


def test_parse_listing_without_cards_yields_nothing():
    assert parse_listing("<html><body><p>nothing here</p></body></html>") == []


def test_parse_listing_resolves_relative_hrefs_and_dedupes():
    html = """
      <a class="col third fundraiser" href="/events/a"><h2>A</h2></a>
      <a class="col third fundraiser" href="/events/a"><h2>A again</h2></a>
      <a class="col third fundraiser" href="/events/b"><h2>B</h2></a>
    """
    entries = parse_listing(html, LISTING_URL)

    assert [e.url for e in entries] == [
        "https://chattzoo.org/events/a",
        "https://chattzoo.org/events/b",
    ]


# --- year resolution -------------------------------------------------------


def test_resolve_year_keeps_upcoming_date_in_current_year():
    assert resolve_year(12, 20, dt.date(2026, 7, 20)) == dt.date(2026, 12, 20)


def test_resolve_year_picks_nearest_past_year_not_next_year():
    # March 22 is 120 days behind 2026-07-20 but 245 days ahead in 2027, so it
    # resolves backwards — the caller then drops it as past.
    assert resolve_year(3, 22, dt.date(2026, 7, 20)) == dt.date(2026, 3, 22)


def test_resolve_year_rolls_over_at_the_december_january_boundary():
    assert resolve_year(1, 10, dt.date(2026, 12, 20)) == dt.date(2027, 1, 10)


def test_resolve_year_skips_impossible_dates():
    # Feb 29 exists in 2028 only, of 2026/2027/2028.
    assert resolve_year(2, 29, dt.date(2027, 7, 1)) == dt.date(2028, 2, 29)
    assert resolve_year(13, 1, dt.date(2026, 7, 1)) is None


# --- detail: fan-out and past filtering ------------------------------------


def test_multi_date_page_fans_out_to_one_event_per_upcoming_date():
    events = parse_detail(
        load("detail_multi.html"),
        "https://www.chattzoo.org/events/adventure-days",
        entry_for(),
        NOW,
    )

    # Page lists March 22, June 28, September 20, December 20; the first two are
    # past as of 2026-07-20.
    assert [e.start_time for e in events] == [
        dt.datetime(2026, 9, 20, 13, 0, tzinfo=UTC),  # 9:00 AM EDT
        dt.datetime(2026, 12, 20, 14, 0, tzinfo=UTC),  # 9:00 AM EST
    ]
    assert [e.end_time for e in events] == [
        dt.datetime(2026, 9, 20, 21, 0, tzinfo=UTC),
        dt.datetime(2026, 12, 20, 22, 0, tzinfo=UTC),
    ]
    assert {e.title for e in events} == {"Adventure Days"}
    assert len({e.description for e in events}) == 1
    assert len({e.source_url for e in events}) == 1


def test_stale_past_date_is_dropped_not_rolled_forward():
    events = parse_detail(
        load("detail_multi.html"),
        "https://www.chattzoo.org/events/adventure-days",
        entry_for(),
        NOW,
    )

    # The leftover March 22 entry must not become a 2027 event.
    assert all(e.start_time.year == 2026 for e in events)
    assert all(e.start_time.month != 3 for e in events)


def test_occurrences_get_distinct_source_event_ids():
    events = parse_detail(
        load("detail_multi.html"),
        "https://www.chattzoo.org/events/adventure-days",
        entry_for(),
        NOW,
    )

    ids = [e.source_event_id for e in events]
    assert ids == ["adventure-days#2026-09-20", "adventure-days#2026-12-20"]
    assert len(set(ids)) == len(ids)


def test_single_date_page_yields_one_event():
    events = parse_detail(
        load("detail_single.html"),
        "https://www.chattzoo.org/events/pirates-parrots-princesses",
        entry_for(),
        NOW,
    )

    (event,) = events
    assert event.title == "Pirates, Parrots & Princesses"
    assert event.start_time == dt.datetime(2026, 8, 8, 14, 0, tzinfo=UTC)  # 10:00 AM EDT
    assert event.end_time == dt.datetime(2026, 8, 8, 17, 0, tzinfo=UTC)
    assert event.source_event_id == "pirates-parrots-princesses#2026-08-08"
    assert "dress-up day" in event.description


def test_page_with_only_past_dates_yields_nothing():
    # August 8 resolves to 2026 (nearest to 2026-09-01) and is over.
    later = dt.datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
    events = parse_detail(
        load("detail_single.html"),
        "https://www.chattzoo.org/events/pirates-parrots-princesses",
        entry_for(),
        later,
    )

    assert events == []


def test_in_progress_event_is_kept():
    # 2026-08-08, between the 10:00 AM start and 1:00 PM end (EDT).
    during = dt.datetime(2026, 8, 8, 15, 0, tzinfo=UTC)
    events = parse_detail(
        load("detail_single.html"),
        "https://www.chattzoo.org/events/pirates-parrots-princesses",
        entry_for(),
        during,
    )

    assert len(events) == 1


def test_unparseable_occurrence_is_skipped_and_siblings_survive():
    events = parse_detail(
        load("detail_unparseable.html"),
        "https://www.chattzoo.org/events/homeschool-days",
        entry_for(),
        NOW,
    )

    # Fixture lists "Date TBA | 10:00 AM - 3:30 PM" and "September 11 | ...".
    (event,) = events
    assert event.start_time == dt.datetime(2026, 9, 11, 14, 0, tzinfo=UTC)


def test_detail_page_without_occurrence_block_yields_nothing():
    assert (
        parse_detail(
            "<html><body><h1>Oops</h1></body></html>", "https://x.test/events/y", entry_for(), NOW
        )
        == []
    )


# --- supplied venue --------------------------------------------------------


def test_every_event_carries_zoo_coordinates_so_ingest_does_not_geocode():
    events = parse_detail(
        load("detail_multi.html"),
        "https://www.chattzoo.org/events/adventure-days",
        entry_for(),
        NOW,
    )

    assert events
    for event in events:
        assert event.latitude == VENUE_LAT
        assert event.longitude == VENUE_LON
        assert event.venue_name == "Chattanooga Zoo"
        assert event.address == "301 North Holtzclaw Avenue, Chattanooga, TN 37404"
        assert event.source_name == SOURCE_NAME
        assert event.tags == []


# --- source-level fetching and failure isolation ---------------------------


def _client_transport(handler) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_fetch_walks_listing_then_detail_pages(monkeypatch):
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        assert request.headers["User-Agent"] == "TestAgent/1.0"
        if request.url.path.endswith("zooevents"):
            return httpx.Response(200, text=load("listing.html"))
        return httpx.Response(200, text=load("detail_single.html"))

    source = ChattZooSource(user_agent="TestAgent/1.0")
    _patch_client(monkeypatch, handler)
    events = await source.fetch()

    assert requested[0] == LISTING_URL
    assert len(requested) == 5  # listing + four detail pages
    assert all(e.source_name == SOURCE_NAME for e in events)


@pytest.mark.asyncio
async def test_failed_listing_fetch_raises_for_run_sources_to_isolate(monkeypatch):
    _patch_client(monkeypatch, lambda request: httpx.Response(503))
    with pytest.raises(httpx.HTTPStatusError):
        await ChattZooSource().fetch()


@pytest.mark.asyncio
async def test_one_failing_detail_page_loses_only_its_own_events(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("zooevents"):
            return httpx.Response(200, text=load("listing.html"))
        if request.url.path.endswith("adventure-days"):
            return httpx.Response(500)
        return httpx.Response(200, text=load("detail_single.html"))

    _patch_client(monkeypatch, handler)
    events = await ChattZooSource().fetch()

    # Three surviving detail pages, each yielding the single-date fixture.
    assert len(events) == 3
    assert all("Pirates" in e.title for e in events)


def _patch_client(monkeypatch, handler) -> None:
    """Route the source's AsyncClient through a MockTransport."""
    original = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = _client_transport(handler)
        return original(*args, **kwargs)

    monkeypatch.setattr("app.events.sources.chattzoo.httpx.AsyncClient", factory)
