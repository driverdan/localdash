"""CitySpark events source, read via The Pulse's portal (``ppid`` 9824).

CitySpark is a commercial events aggregator; this reads the **undocumented
internal JSON API** behind The Pulse's calendar widget at
chattanoogapulse.com/local-events-calendar. It may change or be restricted
without notice. Nothing is circumvented: the API needs no auth, no referer,
and no browser User-Agent — requests are a handful of paged POSTs per refresh
plus one GET for the portal bootstrap. Breakage manifests as zero events plus
logs, contained by run_sources()'s per-source failure isolation.

TIME FIELDS — the payload's ``Z`` lies. ``DateStart``/``DateEnd`` carry a
``Z`` suffix on values that are actually venue-local time (verified live:
``DateStart 08:00:00Z`` beside ``StartUTC 12:00:00Z`` for an 08:00 EDT
event). Using them would shift every event by the UTC offset and corrupt the
``canonical_key`` de-duplication hash. ``StartUTC``/``EndUTC`` are the only
correct time fields; an event without ``StartUTC`` is skipped, never defaulted
to ``DateStart``.

Two endpoints:

* ``POST {PORTAL}/api/events/GetEvents/<slug>`` — the events themselves, paged
  by ``skip``. With ``end`` set the page size is 100; with ``end: null`` the
  API returns only a single day, so ``end`` is always sent.
* ``GET {PORTAL}/PortalScripts/<slug>`` — the widget bootstrap, a JS file
  assigning ``var cSparkLocals = {...}``. Its ``AllTags`` is the portal's tag
  vocabulary (``{id, name, parent}`` tree), which events reference by id.

Events ship exact venue coordinates and curated tag ids, so this source
supplies both on the ``RawEvent`` — ingest neither geocodes nor keyword-tags
these events. Each tag id is rolled up to **one level below its root**
(``Performing Arts > Music > Live Music`` -> ``music``) and lowercased, which
is what merges the portal vocabulary with the existing keyword topics.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re

import httpx

from app.events.sources.base import EventSource, RawEvent, clean_image_url

log = logging.getLogger("localdash.events")

PORTAL = "https://portal.cityspark.com"
SOURCE_NAME = "CitySpark"
PAGE_SIZE = 100
# Guard against a pathological non-terminating pagination loop.
MAX_PAGES = 20
# The bootstrap assigns the portal config before the widget bundle.
_LOCALS_RE = re.compile(r"var\s+cSparkLocals\s*=\s*")


def _parse_utc(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _rollup(tag_id: int, by_id: dict[int, dict]) -> str | None:
    """Resolve a tag id to the name of the node one level below its root.

    A tag that is itself a root resolves to its own name. The walk carries a
    seen-set so a malformed parent cycle terminates; a dangling parent id
    resolves to the deepest node actually reached.
    """
    chain: list[dict] = []
    seen: set[int] = set()
    cursor: int | None = tag_id
    while cursor is not None and cursor in by_id and cursor not in seen:
        seen.add(cursor)
        chain.append(by_id[cursor])
        cursor = chain[-1].get("parent")
    if not chain:
        return None
    if cursor is None and len(chain) >= 2:
        return chain[-2]["name"]  # one level below the root
    # Root tag, dangling parent, or cycle: the last node reached.
    return chain[-1]["name"]


def _rolled_tags(tag_ids: list[int], by_id: dict[int, dict]) -> list[str]:
    names: list[str] = []
    for tag_id in tag_ids:
        name = _rollup(tag_id, by_id)
        if name is None:
            continue  # id absent from the vocabulary
        lowered = name.lower()
        if lowered not in names:
            names.append(lowered)
    return names


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "event"


def _event_url(event: dict, base_url: str) -> str:
    if event.get("PrimaryUrl"):
        return event["PrimaryUrl"]
    for link in event.get("Links") or []:
        if link.get("url"):
            return link["url"]
    if event.get("TicketUrl"):
        return event["TicketUrl"]
    # No outbound URL at all: the widget's own detail route.
    return f"{base_url}details/{_slugify(event.get('Name') or '')}/{event.get('PId')}"


def _event_image(event: dict) -> str | None:
    """The card image: MediumImg, falling back through the other size variants.

    ``MediumImg`` is the purpose-built card variant; the chain guards against a
    partially populated payload before dropping to the first ``Images`` entry.
    """
    for key in ("MediumImg", "LargeImg", "SmallImg"):
        cleaned = clean_image_url(event.get(key))
        if cleaned:
            return cleaned
    for image in event.get("Images") or []:
        cleaned = clean_image_url(image.get("url") if isinstance(image, dict) else None)
        if cleaned:
            return cleaned
    return None


def _join_address(event: dict) -> str | None:
    parts = (event.get("Address"), event.get("CityState"), event.get("Zip"))
    joined = ", ".join(p.strip() for p in parts if isinstance(p, str) and p.strip())
    return joined or None


def parse_payload(payload: dict) -> list[RawEvent]:
    """Extract raw events from a combined payload dict (pure, offline).

    ``payload`` carries the merged ``Value`` event list from the paged
    GetEvents responses plus the bootstrap's ``AllTags`` vocabulary and
    ``baseUrl`` (the portal page hosting the widget).
    """
    by_id = {t["id"]: t for t in payload.get("AllTags") or []}
    base_url = payload.get("baseUrl") or f"{PORTAL}/full-cal/#/"
    events: list[RawEvent] = []
    for event in payload.get("Value") or []:
        start = _parse_utc(event.get("StartUTC"))
        if start is None:
            # Never fall back to DateStart — its "Z" is venue-local time.
            log.warning("cityspark: event without StartUTC skipped: %r", event.get("Name"))
            continue
        events.append(
            RawEvent(
                title=event.get("Name") or "Untitled event",
                description=event.get("Description") or "",
                start_time=start,
                end_time=_parse_utc(event.get("EndUTC")),
                venue_name=event.get("Venue") or None,
                address=_join_address(event),
                latitude=event.get("latitude"),
                longitude=event.get("longitude"),
                image_url=_event_image(event),
                tags=_rolled_tags(event.get("Tags") or [], by_id),
                source_name=SOURCE_NAME,
                source_url=_event_url(event, base_url),
                source_event_id=event.get("Id") or None,
            )
        )
    return events


def parse_bootstrap(script: str) -> dict:
    """Extract the ``cSparkLocals`` JSON object from the bootstrap script."""
    match = _LOCALS_RE.search(script)
    if match is None:
        raise ValueError("cityspark: bootstrap script has no cSparkLocals assignment")
    locals_dict, _ = json.JSONDecoder().raw_decode(script, match.end())
    return locals_dict


class CitySparkSource(EventSource):
    name = SOURCE_NAME

    def __init__(
        self,
        slug: str,
        ppid: int,
        lat: float,
        lon: float,
        radius_miles: float,
        lookahead_days: int,
        timeout: int = 30,
    ):
        self.slug = slug
        self.ppid = ppid
        self.lat = lat
        self.lon = lon
        self.radius_miles = radius_miles
        self.lookahead_days = lookahead_days
        self.timeout = timeout

    def _body(self, start: dt.datetime, end: dt.datetime, skip: int) -> dict:
        return {
            "ppid": self.ppid,
            "start": start.strftime("%Y-%m-%dT%H:%M:%S"),
            # end must always be set: with end null the API caps at one day.
            "end": end.strftime("%Y-%m-%dT%H:%M:%S"),
            "distance": self.radius_miles,
            "lat": self.lat,
            "lng": self.lon,
            "skip": skip,
            "sort": "Time",
            "search": "",
            "category": [],
            "labels": [],
            "pick": False,
            "tps": None,
            "sparks": False,
            "defFilter": "all",
        }

    async def fetch(self) -> list[RawEvent]:
        start = dt.datetime.now(dt.timezone.utc)
        end = start + dt.timedelta(days=self.lookahead_days)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(f"{PORTAL}/PortalScripts/{self.slug}")
            resp.raise_for_status()
            bootstrap = parse_bootstrap(resp.text)

            merged: list[dict] = []
            seen_ids: set[str] = set()
            for page in range(MAX_PAGES):
                resp = await client.post(
                    f"{PORTAL}/api/events/GetEvents/{self.slug}",
                    json=self._body(start, end, page * PAGE_SIZE),
                )
                resp.raise_for_status()
                data = resp.json()
                if not data.get("Success"):
                    raise RuntimeError(f"cityspark: API error: {data.get('ErrorMessage')}")
                value = data.get("Value") or []
                for event in value:
                    if event.get("Id") in seen_ids:
                        continue
                    seen_ids.add(event.get("Id"))
                    merged.append(event)
                if len(value) < PAGE_SIZE:
                    break

        return parse_payload(
            {
                "Value": merged,
                "AllTags": bootstrap.get("AllTags") or [],
                "baseUrl": bootstrap.get("baseUrl"),
            }
        )
