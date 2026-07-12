"""Generic iCal/ICS feed source.

Many venues and civic calendars publish ICS feeds. Point the
``events_ical_feeds`` setting (comma-separated URLs) at them to ingest
automatically. Fetch is async (httpx); parsing is a pure function of the
fetched bytes, separated for offline testability.
"""
from __future__ import annotations

import datetime as dt
import logging

import httpx
from icalendar import Calendar

from app.events.sources.base import EventSource, RawEvent

log = logging.getLogger("localdash.events")


def _to_aware_utc(value) -> dt.datetime | None:
    """Coerce an icalendar date/datetime to an aware UTC datetime."""
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        if value.tzinfo is not None:
            return value.astimezone(dt.timezone.utc)
        return value.replace(tzinfo=dt.timezone.utc)
    if isinstance(value, dt.date):
        return dt.datetime(value.year, value.month, value.day, tzinfo=dt.timezone.utc)
    return None


class ICalSource(EventSource):
    def __init__(self, url: str, name: str | None = None, timeout: int = 20):
        self.url = url
        self.name = name or f"iCal: {url}"
        self.timeout = timeout

    async def fetch(self) -> list[RawEvent]:
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            resp = await client.get(self.url)
            resp.raise_for_status()
        return self.parse(resp.content)

    def parse(self, ics_bytes: bytes) -> list[RawEvent]:
        """Parse ICS bytes into raw events (separated for testability)."""
        cal = Calendar.from_ical(ics_bytes)
        events: list[RawEvent] = []
        for component in cal.walk("VEVENT"):
            start = _to_aware_utc(component.get("dtstart").dt if component.get("dtstart") else None)
            if start is None:
                continue
            end_prop = component.get("dtend")
            uid = str(component.get("uid")) if component.get("uid") else None
            events.append(
                RawEvent(
                    title=str(component.get("summary") or "Untitled event"),
                    description=str(component.get("description") or ""),
                    start_time=start,
                    end_time=_to_aware_utc(end_prop.dt) if end_prop else None,
                    venue_name=str(component.get("location")) if component.get("location") else None,
                    address=str(component.get("location")) if component.get("location") else None,
                    source_name=self.name,
                    source_url=str(component.get("url") or self.url),
                    source_event_id=uid,
                )
            )
        return events
