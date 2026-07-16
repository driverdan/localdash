"""Pluggable event-source interface.

Add a new source by subclassing :class:`EventSource` and returning a list of
:class:`RawEvent` from ``fetch``. The ingest pipeline handles de-duplication,
tagging, geocoding, and persistence.
"""

from __future__ import annotations

import datetime as dt
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from urllib.parse import urlparse

# Basenames of stock/placeholder artwork every source should treat as absent
# (e.g. the Cars and Coffee iCal feed's ``Generic-Car-Show.jpg``). Matched
# case-insensitively as a substring of the URL's final path segment; a miss
# costs only a bland-but-topical image, so the pattern stays deliberately small.
_PLACEHOLDER_RE = re.compile(r"generic|placeholder|default|stock", re.IGNORECASE)


def clean_image_url(url: str | None) -> str | None:
    """Return ``url`` unless it is empty or a known generic/placeholder image.

    Shared by every source so the exclusion rule is applied uniformly: a URL
    whose basename matches the placeholder pattern is treated as no image.
    """
    if not url:
        return None
    url = url.strip()
    if not url:
        return None
    basename = urlparse(url).path.rsplit("/", 1)[-1]
    if _PLACEHOLDER_RE.search(basename):
        return None
    return url


@dataclass
class RawEvent:
    """A single event as reported by one source, before de-duplication.

    A source supplies what it knows and omits the rest; the ingest pipeline
    derives only what is omitted. An event without ``latitude``/``longitude``
    is geocoded from its ``address``; an event with an empty ``tags`` list is
    keyword-tagged from its title and description. Supplied tag names are
    lowercased on ingest so they merge with the keyword topic vocabulary.
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
    latitude: float | None = None
    longitude: float | None = None
    image_url: str | None = None
    tags: list[str] = field(default_factory=list)


class EventSource(ABC):
    """Base class every event source implements."""

    name: str = "base"

    @abstractmethod
    async def fetch(self) -> list[RawEvent]:
        """Return the current set of events from this source."""
        raise NotImplementedError
