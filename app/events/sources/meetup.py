"""Meetup.com event source, backed by the Meetup GraphQL API.

Meetup's legacy REST API has been retired; current access is via the GraphQL
endpoint at ``https://api.meetup.com/gql`` and requires an OAuth2 bearer token
(see https://www.meetup.com/api/authentication/). We use the ``keywordSearch``
query filtered to a latitude/longitude and radius to find events in the
Chattanooga area.

This source emits only an address per event — its GraphQL selection does not
request venue coordinates — so the ingest pipeline's geocoder derives them.
(Sources may supply coordinates directly via ``RawEvent.latitude``/
``longitude``; requesting them from Meetup's ``venue`` selection is a known
follow-up.)
"""

from __future__ import annotations

import logging

from app.events.sources.base import EventSource, RawEvent, clean_image_url
from app.http import make_client
from app.timeutil import parse_iso_utc

log = logging.getLogger(__name__)

ENDPOINT = "https://api.meetup.com/gql"

# keywordSearch returns mixed result types; we only care about Events.
QUERY = """
query EventSearch($filter: SearchConnectionFilter!, $first: Int) {
  keywordSearch(filter: $filter, first: $first) {
    pageInfo { hasNextPage endCursor }
    edges {
      node {
        result {
          ... on Event {
            id
            title
            eventUrl
            dateTime
            description
            featuredEventPhoto { source highResUrl standardUrl baseUrl }
            venue { name address city state }
            group { name }
          }
        }
      }
    }
  }
}
"""


def _photo_url(result: dict) -> str | None:
    """The event photo URL from ``featuredEventPhoto``, or None.

    Meetup's ``Image`` type exposes several sized URLs; we take the first
    populated one. Parsed defensively so a missing/null photo yields no image
    (the field is verified against the live schema only with a configured
    token; a schema drift degrades to imageless events, not an error).
    """
    photo = result.get("featuredEventPhoto")
    if not isinstance(photo, dict):
        return None
    for key in ("source", "highResUrl", "standardUrl", "baseUrl"):
        cleaned = clean_image_url(photo.get(key))
        if cleaned:
            return cleaned
    return None


def _format_address(venue: dict | None) -> str | None:
    """Build a geocodable address string from a Meetup venue."""
    if not venue:
        return None
    parts = [venue.get("address"), venue.get("city"), venue.get("state")]
    address = ", ".join(p for p in parts if p)
    return address or (venue.get("name") or None)


def parse_payload(payload: dict, source_name: str, fallback_url: str) -> list[RawEvent]:
    """Convert a GraphQL response into RawEvents (separated for testability)."""
    search = (payload or {}).get("data", {}).get("keywordSearch") or {}
    edges = search.get("edges") or []

    events: list[RawEvent] = []
    for edge in edges:
        node = (edge or {}).get("node") or {}
        result = node.get("result") or {}
        event_id = result.get("id")
        start = parse_iso_utc(result.get("dateTime"))
        if not event_id or start is None:
            continue  # skip non-Event results or undated entries

        venue = result.get("venue")
        group = result.get("group") or {}
        description = result.get("description") or ""
        if group.get("name"):
            description = f"{group['name']} — {description}".strip(" —")

        events.append(
            RawEvent(
                title=result.get("title") or "Untitled event",
                description=description,
                start_time=start,
                venue_name=(venue or {}).get("name"),
                address=_format_address(venue),
                image_url=_photo_url(result),
                source_name=source_name,
                source_url=result.get("eventUrl") or fallback_url,
                source_event_id=str(event_id),
            )
        )
    return events


class MeetupSource(EventSource):
    name = "Meetup"

    def __init__(
        self,
        token: str,
        lat: float,
        lon: float,
        # Meetup keywordSearch radius; not config — matches the PoC default.
        radius_miles: int = 50,
        query: str = "",
        first: int = 50,
        endpoint: str = ENDPOINT,
        timeout: int = 20,
    ):
        self.token = token
        self.lat = lat
        self.lon = lon
        self.radius_miles = radius_miles
        self.query = query
        self.first = first
        self.endpoint = endpoint
        self.timeout = timeout

    async def fetch(self) -> list[RawEvent]:
        variables = {
            "filter": {
                "query": self.query,
                "lat": self.lat,
                "lon": self.lon,
                "radius": self.radius_miles,
                "source": "EVENTS",
            },
            "first": self.first,
        }
        async with make_client(
            timeout=self.timeout, user_agent=None, follow_redirects=False
        ) as client:
            resp = await client.post(
                self.endpoint,
                json={"query": QUERY, "variables": variables},
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
        return parse_payload(resp.json(), self.name, self.endpoint)
