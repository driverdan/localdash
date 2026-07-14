"""Collector framework — the extensibility seam.

A collector knows how to fetch one source's raw payload and normalize it into a
list of `NormalizedObservation`. The ingestion service and scheduler treat every
source uniformly through this interface, so adding APRS/weather/etc. means writing
one subclass and registering it (see app/collectors/__init__.py).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NormalizedObservation(BaseModel):
    """Source-agnostic representation of one observed state of one entity."""

    external_id: str = Field(..., description="Stable per-source id for the entity")
    category: str = "default"
    label: str | None = None
    lat: float | None = None
    lon: float | None = None
    status: str | None = None
    # The source's own notion of when this state occurred (stored in properties).
    # The canonical hypertable `observed_at` is stamped by the ingest service.
    source_time: datetime | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class BaseCollector(ABC):
    """Subclass per data source."""

    #: Stable identifier used as the DB source_key (e.g. "hc911").
    source_key: str
    #: Human-readable name shown in the dashboard.
    name: str
    #: Default polling cadence in seconds.
    poll_interval: int = 60

    @abstractmethod
    async def fetch(self) -> Any:
        """Return the raw payload from the upstream source (network I/O)."""

    @abstractmethod
    def normalize(self, raw: Any) -> list[NormalizedObservation]:
        """Convert a raw payload into normalized observations (pure, no I/O)."""

    async def collect(self) -> list[NormalizedObservation]:
        """Convenience: fetch + normalize."""
        return self.normalize(await self.fetch())
