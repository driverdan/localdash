"""Response models for the events API (/api/v1/events).

Fields are declared in the order the JSON has always carried them; see
app/contracts.py for the shared base model and the datetime rule.
"""

from __future__ import annotations

from app.contracts import ApiModel, IsoDateTime


class EventLink(ApiModel):
    """One origin that reported the event."""

    source_name: str
    source_url: str


class EventItem(ApiModel):
    id: int
    title: str
    description: str
    starts_at: IsoDateTime
    ends_at: IsoDateTime | None
    venue_name: str | None
    address: str | None
    image_url: str | None
    latitude: float | None
    longitude: float | None
    tags: list[str]
    links: list[EventLink]
    distance_miles: float | None


class Origin(ApiModel):
    """The point distances are measured from."""

    lat: float
    lon: float


class EventsResponse(ApiModel):
    count: int
    origin: Origin
    items: list[EventItem]


class TagsResponse(ApiModel):
    tags: list[str]
