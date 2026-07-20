"""Offline tests for the Meetup source: parse half and token-gated registration."""

import datetime as dt

from app.config import Settings
from app.events.sources import build_sources
from app.events.sources.ical import ICalSource
from app.events.sources.meetup import MeetupSource

UTC = dt.timezone.utc

# A representative slice of a Meetup GraphQL keywordSearch response.
SAMPLE_PAYLOAD = {
    "data": {
        "keywordSearch": {
            "pageInfo": {"hasNextPage": False, "endCursor": None},
            "edges": [
                {
                    "node": {
                        "result": {
                            "id": "302000001",
                            "title": "Chattanooga Python Coders Meetup",
                            "eventUrl": "https://www.meetup.com/chatt-python/events/302000001/",
                            "dateTime": "2026-07-15T18:30-04:00",
                            "description": "Monthly meetup for local software developers.",
                            "featuredEventPhoto": {
                                "source": "https://secure.meetupstatic.com/photos/event/big.jpg"
                            },
                            "venue": {
                                "name": "Society of Work",
                                "address": "1800 Rossville Ave",
                                "city": "Chattanooga",
                                "state": "TN",
                            },
                            "group": {"name": "Chattanooga Python Coders"},
                        }
                    }
                },
                # A non-Event result (e.g. a group) — must be ignored.
                {"node": {"result": {}}},
            ],
        }
    }
}


def _source() -> MeetupSource:
    return MeetupSource(token="test-token", lat=35.0456, lon=-85.3097)


def test_parse_extracts_event_fields():
    events = _source().parse(SAMPLE_PAYLOAD)
    assert len(events) == 1

    event = events[0]
    assert event.title == "Chattanooga Python Coders Meetup"
    # 18:30 at UTC-4 -> 22:30 UTC.
    assert event.start_time == dt.datetime(2026, 7, 15, 22, 30, tzinfo=UTC)
    assert event.address == "1800 Rossville Ave, Chattanooga, TN"
    assert event.venue_name == "Society of Work"
    assert event.source_name == "Meetup"
    assert event.source_url.endswith("/302000001/")
    assert event.source_event_id == "302000001"
    # The group name is prefixed onto the description.
    assert event.description.startswith("Chattanooga Python Coders")
    assert event.image_url == "https://secure.meetupstatic.com/photos/event/big.jpg"


def test_parse_handles_empty_or_malformed_payload():
    assert _source().parse({}) == []
    assert _source().parse({"data": {"keywordSearch": {"edges": []}}}) == []


def test_missing_photo_yields_no_image():
    payload = {
        "data": {
            "keywordSearch": {
                "edges": [
                    {
                        "node": {
                            "result": {
                                "id": "1",
                                "title": "No Photo Meetup",
                                "eventUrl": "https://www.meetup.com/g/events/1/",
                                "dateTime": "2026-07-15T18:30-04:00",
                            }
                        }
                    }
                ]
            }
        }
    }
    (event,) = _source().parse(payload)
    assert event.image_url is None


def _settings(**overrides) -> Settings:
    """Settings isolated from .env and the ambient environment."""
    base = dict(
        events_ical_feeds="",
        events_tribe_calendars="",
        events_meetup_token="",
        events_meetup_query="",
    )
    base.update(overrides)
    return Settings(_env_file=None, **base)


def test_build_sources_includes_meetup_only_when_token_set():
    assert not any(isinstance(s, MeetupSource) for s in build_sources(_settings()))

    sources = build_sources(_settings(events_meetup_token="a-token"))
    assert any(isinstance(s, MeetupSource) for s in sources)


def test_build_sources_creates_one_ical_source_per_url():
    sources = build_sources(
        _settings(events_ical_feeds="https://a.example/cal.ics, https://b.example/cal.ics,")
    )
    ical = [s for s in sources if isinstance(s, ICalSource)]
    assert [s.url for s in ical] == ["https://a.example/cal.ics", "https://b.example/cal.ics"]


def test_build_sources_leaves_only_the_scrapers_when_nothing_configured():
    # The CarCruiseFinder and Chattanooga Zoo scrapers have no config gate;
    # emptying the configurable sources (and disabling CitySpark) leaves them.
    from app.events.sources.carcruisefinder import CarCruiseFinderSource
    from app.events.sources.chattzoo import ChattZooSource

    sources = build_sources(_settings(events_cityspark_enabled=False))
    assert [type(s) for s in sources] == [CarCruiseFinderSource, ChattZooSource]


def test_build_sources_default_registers_tennessee_car_feed():
    """A fresh install (no override) ingests the shipped default feed."""
    sources = build_sources(Settings(_env_file=None))
    ical_sources = [s for s in sources if isinstance(s, ICalSource)]
    assert len(ical_sources) == 1
    assert (
        ical_sources[0].url == "https://carsandcoffeeevents.com/events/category/tennessee/?ical=1"
    )


def test_build_sources_empty_ical_feeds_yields_no_ical_sources():
    """Explicitly empty EVENTS_ICAL_FEEDS disables iCal ingestion entirely."""
    sources = build_sources(_settings(events_ical_feeds=""))
    assert not any(isinstance(s, ICalSource) for s in sources)
