"""Meetup.com event source, backed by the Meetup GraphQL API.

Meetup's legacy REST API has been retired; current access is via the GraphQL
endpoint at ``https://api.meetup.com/gql`` and requires an OAuth2 bearer token
(see https://www.meetup.com/api/authentication/). We use the ``keywordSearch``
query filtered to a latitude/longitude and radius to find events in the
Chattanooga area.

In keeping with the rest of the pipeline, only an address is emitted per event;
coordinates are derived later by the ingest pipeline's geocoder.
"""

from __future__ import annotations

import datetime as dt
import logging

import httpx

from app.events.sources.base import EventSource, RawEvent

log = logging.getLogger("localdash.events")

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
            venue { name address city state }
            group { name }
          }
        }
      }
    }
  }
}
"""


def _to_aware_utc(value: str | None) -> dt.datetime | None:
    """Parse a Meetup ISO-8601 datetime (with offset) into aware UTC."""
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        return parsed.astimezone(dt.timezone.utc)
    return parsed.replace(tzinfo=dt.timezone.utc)


def _format_address(venue: dict | None) -> str | None:
    """Build a geocodable address string from a Meetup venue."""
    if not venue:
        return None
    parts = [venue.get("address"), venue.get("city"), venue.get("state")]
    address = ", ".join(p for p in parts if p)
    return address or (venue.get("name") or None)


class MeetupSource(EventSource):
    name = "Meetup"

    def __init__(
        self,
        token: str,
        lat: float,
        lon: float,
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
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                self.endpoint,
                json={"query": QUERY, "variables": variables},
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
        return self.parse(resp.json())

    def parse(self, payload: dict) -> list[RawEvent]:
        """Convert a GraphQL response into RawEvents (separated for testability)."""
        search = (payload or {}).get("data", {}).get("keywordSearch") or {}
        edges = search.get("edges") or []

        events: list[RawEvent] = []
        for edge in edges:
            node = (edge or {}).get("node") or {}
            result = node.get("result") or {}
            event_id = result.get("id")
            start = _to_aware_utc(result.get("dateTime"))
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
                    source_name=self.name,
                    source_url=result.get("eventUrl") or self.endpoint,
                    source_event_id=str(event_id),
                )
            )
        return events
