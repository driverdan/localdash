"""Response models and refresh results for the events API (/api/v1/events).

Fields are declared in the order the JSON has always carried them; see
app/contracts.py for the shared base model and the datetime rule. The refresh
results are plain frozen dataclasses (built in-process, never from untrusted
input); FastAPI serves EventsRefreshResult directly as a response model.
"""

from __future__ import annotations

from dataclasses import dataclass

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


@dataclass(frozen=True, slots=True)
class UpsertStats:
    """What upsert_raw_events (and so run_sources) did with one batch."""

    created: int
    merged: int
    skipped_far: int


@dataclass(frozen=True, slots=True)
class GeocodeRetryStats:
    """What one retry_failed_geocodes pass did."""

    retried: int
    resolved: int


@dataclass(frozen=True, slots=True)
class EventsRefreshResult:
    """One events refresh cycle; the body of POST /api/v1/events/refresh."""

    created: int
    merged: int
    skipped_far: int
    retried: int
    resolved: int
    reconciled: int

    @property
    def changed_visible_data(self) -> bool:
        """Whether the cycle changed data clients can see (and so should ping)."""
        return any((self.created, self.merged, self.resolved, self.reconciled))
