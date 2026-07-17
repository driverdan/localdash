"""The Events Calendar (tribe) REST source for WordPress sites.

Any WordPress site running The Events Calendar plugin exposes
``GET <base_url>/wp-json/tribe/events/v1/events`` with date-window filtering
(``start_date``/``end_date``, interpreted in site-local time — day-boundary
slop is harmless because the window is a fetch horizon, not a display filter)
and ``per_page``/``page`` pagination reported via ``total_pages``. Calendars
are configured with the ``events_tribe_calendars`` setting (``Name=BaseURL``
entries); the default is the Chattanooga Public Library. Verified 2026-07: the
endpoint needs no auth and accepts the default User-Agent, and each
recurring-series occurrence is its own post with a distinct ``id``, so
occurrence ids are safe as source event ids.

Venues ship a full postal address and usually ``geo_lat``/``geo_lng``, and
events carry curated category names, so this source supplies coordinates and
tags on the ``RawEvent`` when present — ingest then neither geocodes nor
keyword-tags those events. Descriptions are HTML and titles carry encoded
entities (both reduced to plain text here; the frontend renders descriptions
as text). Breakage from a plugin update manifests as zero events plus logs,
contained by run_sources()'s per-source failure isolation.
"""

from __future__ import annotations

import datetime as dt
import html as html_lib
import logging

import httpx
from bs4 import BeautifulSoup

from app.events.sources.base import EventSource, RawEvent, clean_image_url

log = logging.getLogger("localdash.events")

PAGE_SIZE = 50  # the API's per_page maximum
# Guard against a pathological non-terminating pagination loop.
MAX_PAGES = 10


def _parse_utc(value: str | None) -> dt.datetime | None:
    """Parse the API's naive ``YYYY-MM-DD HH:MM:SS`` UTC fields."""
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _strip_html(fragment: str) -> str:
    if not fragment:
        return ""
    return BeautifulSoup(fragment, "html.parser").get_text(" ", strip=True)


def _coord(value) -> float | None:
    # The API emits false (not null) for absent venue geo fields.
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _join_address(venue: dict) -> str | None:
    parts = (venue.get("address"), venue.get("city"), venue.get("stateprovince"), venue.get("zip"))
    joined = ", ".join(p.strip() for p in parts if isinstance(p, str) and p.strip())
    return joined or None


def _category_tags(event: dict) -> list[str]:
    names: list[str] = []
    for category in event.get("categories") or []:
        name = category.get("name") if isinstance(category, dict) else None
        if not name:
            continue
        lowered = html_lib.unescape(name).lower()
        if lowered not in names:
            names.append(lowered)
    return names


def parse_page(payload: dict, source_name: str) -> list[RawEvent]:
    """Extract raw events from one ``events`` page payload (pure, offline)."""
    events: list[RawEvent] = []
    for event in payload.get("events") or []:
        start = _parse_utc(event.get("utc_start_date"))
        if start is None:
            log.warning("tribe: event without utc_start_date skipped: %r", event.get("title"))
            continue
        # Absent sub-objects arrive as [] or false, not null.
        venue = event.get("venue")
        if not isinstance(venue, dict):
            venue = {}
        image = event.get("image")
        image_url = image.get("url") if isinstance(image, dict) else None
        events.append(
            RawEvent(
                title=html_lib.unescape(event.get("title") or "") or "Untitled event",
                description=_strip_html(event.get("description") or ""),
                start_time=start,
                end_time=_parse_utc(event.get("utc_end_date")),
                venue_name=venue.get("venue") or None,
                address=_join_address(venue),
                latitude=_coord(venue.get("geo_lat")),
                longitude=_coord(venue.get("geo_lng")),
                image_url=clean_image_url(image_url),
                tags=_category_tags(event),
                source_name=source_name,
                source_url=event.get("url") or "",
                source_event_id=str(event["id"]) if event.get("id") is not None else None,
            )
        )
    return events


class TribeEventsSource(EventSource):
    def __init__(self, base_url: str, name: str, lookahead_days: int, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.name = name
        self.lookahead_days = lookahead_days
        self.timeout = timeout

    async def fetch(self) -> list[RawEvent]:
        today = dt.datetime.now(dt.timezone.utc).date()
        params = {
            "start_date": today.isoformat(),
            "end_date": (today + dt.timedelta(days=self.lookahead_days)).isoformat(),
            "per_page": PAGE_SIZE,
        }
        endpoint = f"{self.base_url}/wp-json/tribe/events/v1/events"
        events: list[RawEvent] = []
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            for page in range(1, MAX_PAGES + 1):
                resp = await client.get(endpoint, params={**params, "page": page})
                resp.raise_for_status()
                payload = resp.json()
                events.extend(parse_page(payload, self.name))
                if page >= int(payload.get("total_pages") or 1):
                    break
        return events
