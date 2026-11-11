"""Offline tests for the iCal source's parse half (ported from the PoC)."""

import datetime as dt

import httpx
import pytest

from app.events.sources.ical import ICalSource, parse_calendar

UTC = dt.UTC

ICS_SAMPLE = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//test//test//EN
BEGIN:VEVENT
UID:abc-123
SUMMARY:Downtown Art Walk
DTSTART:20260710T180000Z
DTEND:20260710T210000Z
LOCATION:Bluff View Art District
URL:https://example.com/artwalk
END:VEVENT
END:VCALENDAR
"""

ICS_UNDATED = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//test//test//EN
BEGIN:VEVENT
UID:no-date
SUMMARY:Mystery Event
END:VEVENT
BEGIN:VEVENT
UID:dated
SUMMARY:Real Event
DTSTART:20260710T180000Z
END:VEVENT
END:VCALENDAR
"""

ICS_ALL_DAY = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//test//test//EN
BEGIN:VEVENT
UID:all-day
SUMMARY:All Day Festival
DTSTART;VALUE=DATE:20260704
END:VEVENT
END:VCALENDAR
"""


ICS_WITH_IMAGE = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//test//test//EN
BEGIN:VEVENT
UID:img-1
SUMMARY:Gallery Opening
DTSTART:20260710T180000Z
ATTACH;FMTTYPE=image/jpeg:https://example.com/photos/opening.jpg
END:VEVENT
END:VCALENDAR
"""

ICS_GENERIC_IMAGE = b"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//test//test//EN
BEGIN:VEVENT
UID:generic-1
SUMMARY:Cars and Coffee
DTSTART:20260710T180000Z
ATTACH;FMTTYPE=image/jpeg:https://example.com/img/Generic-Car-Show.jpg
END:VEVENT
END:VCALENDAR
"""


FEED_URL = "https://example.com/feed.ics"
SOURCE_NAME = f"iCal: {FEED_URL}"  # ICalSource's default name for FEED_URL


def _source() -> ICalSource:
    return ICalSource(FEED_URL)


def test_image_attach_is_parsed():
    (event,) = parse_calendar(ICS_WITH_IMAGE, SOURCE_NAME, FEED_URL)
    assert event.image_url == "https://example.com/photos/opening.jpg"


def test_generic_image_attach_is_treated_as_absent():
    (event,) = parse_calendar(ICS_GENERIC_IMAGE, SOURCE_NAME, FEED_URL)
    assert event.image_url is None


def test_event_without_attach_has_no_image():
    (event,) = parse_calendar(ICS_SAMPLE, SOURCE_NAME, FEED_URL)
    assert event.image_url is None


def test_parses_event_fields():
    events = parse_calendar(ICS_SAMPLE, SOURCE_NAME, FEED_URL)
    assert len(events) == 1
    event = events[0]
    assert event.title == "Downtown Art Walk"
    assert event.start_time == dt.datetime(2026, 7, 10, 18, 0, tzinfo=UTC)
    assert event.end_time == dt.datetime(2026, 7, 10, 21, 0, tzinfo=UTC)
    assert event.venue_name == "Bluff View Art District"
    assert event.address == "Bluff View Art District"
    assert event.source_url == "https://example.com/artwalk"
    assert event.source_event_id == "abc-123"


def test_undated_components_are_skipped():
    events = parse_calendar(ICS_UNDATED, SOURCE_NAME, FEED_URL)
    assert [e.title for e in events] == ["Real Event"]
    # No per-event URL -> the feed URL is the link.
    assert events[0].source_url == "https://example.com/feed.ics"


def test_date_only_start_becomes_midnight_utc():
    events = parse_calendar(ICS_ALL_DAY, SOURCE_NAME, FEED_URL)
    assert events[0].start_time == dt.datetime(2026, 7, 4, 0, 0, tzinfo=UTC)


# --- fetch() (through the mock_http fixture) ---


async def test_fetch_parses_the_downloaded_calendar(mock_http):
    mock_http.install(lambda request: httpx.Response(200, content=ICS_SAMPLE))

    events = await _source().fetch()

    assert [str(r.url) for r in mock_http.requests] == ["https://example.com/feed.ics"]
    assert [e.title for e in events] == [
        e.title for e in parse_calendar(ICS_SAMPLE, SOURCE_NAME, FEED_URL)
    ]
    assert events


async def test_fetch_non_2xx_raises(mock_http):
    mock_http.install(lambda request: httpx.Response(404))

    with pytest.raises(httpx.HTTPStatusError):
        await _source().fetch()
