"""Pluggable event-source interface.

Add a new source by subclassing :class:`EventSource` and returning a list of
:class:`RawEvent` from ``fetch``. The ingest pipeline handles de-duplication,
tagging, geocoding, and persistence.
"""
from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class RawEvent:
    """A single event as reported by one source, before de-duplication.

    Sources provide a human-readable ``address`` (and optional ``venue_name``);
    coordinates are derived later by the ingest pipeline's geocoder.
    ``start_time``/``end_time`` are timezone-aware UTC datetimes.
    """

    title: str
    start_time: dt.datetime
    source_name: str
    source_url: str
    description: str = ""
    end_time: dt.datetime | None = None
    venue_name: str | None = None
    address: str | None = None
    source_event_id: str | None = None


class EventSource(ABC):
    """Base class every event source implements."""

    name: str = "base"

    @abstractmethod
    async def fetch(self) -> list[RawEvent]:
        """Return the current set of events from this source."""
        raise NotImplementedError
