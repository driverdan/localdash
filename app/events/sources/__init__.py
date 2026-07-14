"""Registry of the event sources used by the scheduled ingest job.

Production ingests only real, configured sources:
  * iCal feeds via the ``events_ical_feeds`` setting
  * Meetup.com via ``events_meetup_token``
  * CarCruiseFinder's Chattanooga tag listing (always on, like any source whose
    prerequisites are met — its only prerequisite is the events feature itself)

There is intentionally no sample/seed data here — fixtures live in the test
suite only.
"""

from __future__ import annotations

from app.config import Settings
from app.events import CHATTANOOGA_CENTER, MEETUP_RADIUS_MILES
from app.events.sources.base import EventSource
from app.events.sources.carcruisefinder import CarCruiseFinderSource
from app.events.sources.ical import ICalSource
from app.events.sources.meetup import MeetupSource


def build_sources(settings: Settings) -> list[EventSource]:
    """Build the list of real sources to ingest on each run."""
    sources: list[EventSource] = [CarCruiseFinderSource()]

    for url in filter(None, (u.strip() for u in settings.events_ical_feeds.split(","))):
        sources.append(ICalSource(url))

    if settings.events_meetup_token:
        sources.append(
            MeetupSource(
                token=settings.events_meetup_token,
                lat=CHATTANOOGA_CENTER[0],
                lon=CHATTANOOGA_CENTER[1],
                radius_miles=MEETUP_RADIUS_MILES,
                query=settings.events_meetup_query,
            )
        )

    return sources
