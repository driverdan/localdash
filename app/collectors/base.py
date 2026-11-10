"""Collector framework — the extensibility seam.

A collector knows how to fetch one source's raw payload and normalize it into a
list of `NormalizedObservation`. The ingestion service and app/collect.py treat every
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
    # Explicit GeoJSON geometry for area sources (Polygon / MultiPolygon / etc.).
    # Point sources set lat/lon and leave this None. Explicit `geometry` wins when
    # both are set. Consumers read `resolved_geometry`, never these raw fields.
    geometry: dict | None = None
    status: str | None = None
    # The source's own notion of when this state occurred (stored in properties).
    # The canonical hypertable `observed_at` is stamped by the ingest service.
    source_time: datetime | None = None
    properties: dict[str, Any] = Field(default_factory=dict)

    @property
    def resolved_geometry(self) -> dict[str, Any] | None:
        """The observation's geometry as a GeoJSON geometry dict.

        `geometry` when set, else a `Point` built from `lon`/`lat` when both are
        set, else None (null geometry).
        """
        if self.geometry is not None:
            return self.geometry
        if self.lat is not None and self.lon is not None:
            return {"type": "Point", "coordinates": [self.lon, self.lat]}
        return None


def as_float(value: Any) -> float | None:
    """``float(value)``, or None when it cannot be converted or is NaN."""
    try:
        f = float(value)
    except TypeError, ValueError:
        return None
    return f if f == f else None  # reject NaN


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
