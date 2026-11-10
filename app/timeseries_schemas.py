"""Response models and the collector run result for the timeseries API (/api/v1/timeseries).

The timeseries code sits at the top level of app/ (ingest.py, geojson.py,
collect.py, api/timeseries.py), so its models live here rather than in a
package schemas module. The GeoJSON routes' documentation-only models are in
app/geojson.py, beside the helpers that build those dicts.

Fields are declared in the order the JSON has always carried them; see
app/contracts.py for the shared base model and the datetime rule. JSONB blobs
(`latest_properties`, a track point's `properties`) and GeoJSON geometries stay
open objects: they carry arbitrary source fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.contracts import ApiModel, IsoDateTime


class EntitySnapshot(ApiModel):
    """GET /entities/{id}: one entity without its track."""

    id: int
    source: str
    external_id: str
    category: str
    label: str | None
    is_active: bool
    first_seen_at: IsoDateTime | None
    last_seen_at: IsoDateTime | None
    latest_properties: dict[str, Any] | None


class TrackPoint(ApiModel):
    """One observation in GET /entities/{id}/track."""

    observed_at: IsoDateTime
    status: str | None
    geometry: dict[str, Any] | None
    # Point convenience fields, null for non-point geometry. Taken straight from
    # the GeoJSON coordinates, so an integral coordinate stays an integer.
    lon: int | float | None
    lat: int | float | None
    properties: dict[str, Any] | None


class SourceStatus(ApiModel):
    """One collector's row in GET /sources, with its last-run telemetry."""

    key: str
    name: str
    enabled: bool
    poll_interval_seconds: int
    last_run_at: IsoDateTime | None
    last_status: str | None
    last_error: str | None
    last_count: int | None


@dataclass(frozen=True, slots=True)
class CollectorRun:
    """One collection cycle (app/collect.py:run_collector); the body of
    POST /api/v1/timeseries/sources/{key}/refresh."""

    source: str
    status: Literal["ok", "error"]
    error: str | None
    count: int
