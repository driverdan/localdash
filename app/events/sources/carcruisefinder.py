"""CarCruiseFinder Chattanooga-tag scraper source.

The site's machine endpoints (The Events Calendar iCal export and
``/wp-json/tribe/events/v1/events``) are blocked by a Cloudflare WAF (403), so
this source scrapes the human-facing listing page instead — and only that one
page: the listing embeds a complete schema.org ``Event`` JSON-LD array for
every listed event (names, DST-correct offsets, venue names, full postal
addresses). Per-event detail pages are deliberately NOT fetched — their own
JSON-LD was observed carrying wrong UTC offsets (EST on August dates), which
would shift canonical keys and break cross-source dedup.

The site returns 403 to generic/short User-Agents on its human-facing pages,
so requests carry a fixed realistic browser UA (same precedent as the
ChattNews/TownNews feeds in app/news/registry.py) — the minimum that works; no
further WAF circumvention. The source is inherently fragile (WAF policy or
markup changes break it at any time); breakage manifests as zero events plus
logs, contained by run_sources()'s per-source failure isolation.
"""

from __future__ import annotations

import datetime as dt
import html as html_lib
import json
import logging
from typing import Any, Iterator
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

from app.events.sources.base import EventSource, RawEvent, clean_image_url

log = logging.getLogger("localdash.events")

LISTING_URL = "https://carcruisefinder.com/car-shows/tag/chattanooga-tn/"
# The site 403s generic UAs; a realistic desktop browser UA is required.
BROWSER_UA = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
SOURCE_NAME = "CarCruiseFinder"
# These are local car meets; naive JSON-LD datetimes are venue-local.
LOCAL_TZ = ZoneInfo("America/New_York")


def _iter_event_nodes(data: Any) -> Iterator[dict]:
    """Yield schema.org Event nodes from any common JSON-LD shape."""
    if isinstance(data, list):
        for item in data:
            yield from _iter_event_nodes(item)
    elif isinstance(data, dict):
        if data.get("@type") == "Event":
            yield data
        yield from _iter_event_nodes(data.get("@graph", []))


def _to_aware_utc(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=LOCAL_TZ)
    return parsed.astimezone(dt.timezone.utc)


def _clean_text(value: str | None) -> str:
    """Decode entities, strip any markup, and collapse whitespace."""
    if not value:
        return ""
    text = BeautifulSoup(html_lib.unescape(value), "html.parser").get_text()
    return " ".join(text.split())


def _join_address(location: dict) -> str | None:
    address = location.get("address")
    if isinstance(address, str):
        return _clean_text(address) or None
    if not isinstance(address, dict):
        return None
    parts = (
        address.get(key)
        for key in (
            "streetAddress",
            "addressLocality",
            "addressRegion",
            "postalCode",
            "addressCountry",
        )
    )
    joined = ", ".join(_clean_text(p) for p in parts if isinstance(p, str) and p.strip())
    return joined or None


def _image_url(image: Any) -> str | None:
    """The event image from a schema.org ``image`` value (string, list, or object)."""
    if isinstance(image, list):
        for item in image:
            cleaned = _image_url(item)
            if cleaned:
                return cleaned
        return None
    if isinstance(image, dict):
        image = image.get("url")
    return clean_image_url(image if isinstance(image, str) else None)


def parse_listing(html: str, listing_url: str = LISTING_URL) -> list[RawEvent]:
    """Extract raw events from the listing page's Event JSON-LD (pure, offline)."""
    soup = BeautifulSoup(html, "html.parser")
    events: list[RawEvent] = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except ValueError:
            log.warning("carcruisefinder: unparseable JSON-LD block skipped")
            continue
        for node in _iter_event_nodes(data):
            start = _to_aware_utc(node.get("startDate"))
            if start is None:
                log.warning(
                    "carcruisefinder: event without start date skipped: %r", node.get("name")
                )
                continue
            location = node.get("location") if isinstance(node.get("location"), dict) else {}
            url = node.get("url") or listing_url
            events.append(
                RawEvent(
                    title=_clean_text(node.get("name")) or "Untitled event",
                    description=_clean_text(node.get("description")),
                    start_time=start,
                    end_time=_to_aware_utc(node.get("endDate")),
                    venue_name=_clean_text(location.get("name")) or None,
                    address=_join_address(location),
                    image_url=_image_url(node.get("image")),
                    source_name=SOURCE_NAME,
                    source_url=url,
                    source_event_id=urlparse(url).path.strip("/") or None,
                )
            )
    return events


class CarCruiseFinderSource(EventSource):
    name = SOURCE_NAME

    def __init__(self, url: str = LISTING_URL, timeout: int = 20):
        self.url = url
        self.timeout = timeout

    async def fetch(self) -> list[RawEvent]:
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            resp = await client.get(self.url, headers={"User-Agent": BROWSER_UA})
            resp.raise_for_status()
        return parse_listing(resp.text, self.url)
