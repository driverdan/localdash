"""Offline tests for the iCal source's parse half (ported from the PoC)."""

import datetime as dt

from app.events.sources.ical import ICalSource

UTC = dt.timezone.utc

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


def _source() -> ICalSource:
    return ICalSource("https://example.com/feed.ics")


def test_parses_event_fields():
    events = _source().parse(ICS_SAMPLE)
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
    events = _source().parse(ICS_UNDATED)
    assert [e.title for e in events] == ["Real Event"]
    # No per-event URL -> the feed URL is the link.
    assert events[0].source_url == "https://example.com/feed.ics"


def test_date_only_start_becomes_midnight_utc():
    events = _source().parse(ICS_ALL_DAY)
    assert events[0].start_time == dt.datetime(2026, 7, 4, 0, 0, tzinfo=UTC)
