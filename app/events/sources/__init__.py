"""Registry of the event sources used by the scheduled ingest job.

Production ingests only real, configured sources:
  * iCal feeds via the ``events_ical_feeds`` setting
  * The Events Calendar (tribe) REST calendars via ``events_tribe_calendars``
    (``Name=BaseURL`` entries; malformed entries are skipped with a warning)
  * Meetup.com via ``events_meetup_token``
  * The Pulse's CitySpark calendar via ``events_cityspark_enabled`` (large
    enough that an operator may reasonably want it off)
  * CarCruiseFinder's Chattanooga tag listing and the Chattanooga Zoo's events
    page (always on, like any source whose prerequisites are met — their only
    prerequisite is the events feature itself)

There is intentionally no sample/seed data here — fixtures live in the test
suite only.
"""

from __future__ import annotations

import logging

from app.config import Settings
from app.events import MEETUP_RADIUS_MILES
from app.events.sources.base import EventSource
from app.events.sources.carcruisefinder import CarCruiseFinderSource
from app.events.sources.chattzoo import ChattZooSource
from app.events.sources.cityspark import CitySparkSource
from app.events.sources.ical import ICalSource
from app.events.sources.meetup import MeetupSource
from app.events.sources.tribe import TribeEventsSource

log = logging.getLogger("localdash.events")


def build_sources(settings: Settings) -> list[EventSource]:
    """Build the list of real sources to ingest on each run."""
    sources: list[EventSource] = [
        CarCruiseFinderSource(),
        ChattZooSource(user_agent=settings.user_agent),
    ]

    if settings.events_cityspark_enabled:
        sources.append(
            CitySparkSource(
                slug=settings.events_cityspark_slug,
                ppid=settings.events_cityspark_ppid,
                lat=settings.center_lat,
                lon=settings.center_lon,
                radius_miles=settings.events_cityspark_radius_miles,
                lookahead_days=settings.events_cityspark_lookahead_days,
            )
        )

    for url in filter(None, (u.strip() for u in settings.events_ical_feeds.split(","))):
        sources.append(ICalSource(url))

    for entry in filter(None, (e.strip() for e in settings.events_tribe_calendars.split(","))):
        name, sep, base_url = entry.partition("=")
        if not sep or not name.strip() or not base_url.strip():
            log.warning("events_tribe_calendars entry %r is not Name=BaseURL; skipped", entry)
            continue
        sources.append(
            TribeEventsSource(
                base_url=base_url.strip(),
                name=name.strip(),
                lookahead_days=settings.events_tribe_lookahead_days,
            )
        )

    if settings.events_meetup_token:
        sources.append(
            MeetupSource(
                token=settings.events_meetup_token,
                lat=settings.center_lat,
                lon=settings.center_lon,
                radius_miles=MEETUP_RADIUS_MILES,
                query=settings.events_meetup_query,
            )
        )

    return sources
