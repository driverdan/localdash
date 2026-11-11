"""Helpers for emitting GeoJSON (RFC 7946) Features / FeatureCollections.

The models at the bottom document these dicts in OpenAPI only. The GeoJSON
routes return the dicts as built here and never validate them against the
models: a response can hold tens of thousands of features whose properties are
mostly open source fields, so validation would cost a second pass for little
checking. Each properties model names only the keys the system adds and allows
any others. tests/test_api_contracts.py checks a real response against them.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any, Literal

from pydantic import ConfigDict

from app.contracts import ApiModel, IsoDateTime


def feature_geom(
    geometry: dict[str, Any] | None, properties: dict[str, Any], fid: Any = None
) -> dict:
    """A GeoJSON Feature wrapping an already-formed geometry (Point, Polygon, …)."""
    feat: dict[str, Any] = {"type": "Feature", "geometry": geometry, "properties": properties}
    if fid is not None:
        feat["id"] = fid
    return feat


def entity_properties(
    raw: dict[str, Any] | None,
    *,
    id: Any,
    source: str,
    external_id: str,
    category: str | None,
    label: str | None,
    last_seen_at: datetime | None,
    active: bool,
    status: str | None,
) -> dict[str, Any]:
    """Entity feature properties — the one contract shared by REST and live diffs.

    Raw source fields come first so our authoritative keys always override them
    (an upstream item's own `id`, for example, must not replace the entity id).
    """
    return {
        **(raw or {}),
        "id": id,
        "source": source,
        "external_id": external_id,
        "category": category,
        "label": label,
        "last_seen_at": last_seen_at.isoformat() if last_seen_at else None,
        "active": active,
        "status": status,
    }


def feature_collection(features: Iterable[dict]) -> dict:
    return {"type": "FeatureCollection", "features": list(features)}


# --- OpenAPI documentation models (never used to validate a response) ---------


class EntityProperties(ApiModel):
    """The keys entity_properties() adds; source-specific keys pass through."""

    model_config = ConfigDict(extra="allow")

    id: int
    source: str
    external_id: str
    category: str | None
    label: str | None
    last_seen_at: IsoDateTime | None
    active: bool
    status: str | None


class EntityFeature(ApiModel):
    type: Literal["Feature"]
    geometry: dict[str, Any] | None
    properties: EntityProperties
    id: int


class EntityFeatureCollection(ApiModel):
    """GET /timeseries/entities."""

    type: Literal["FeatureCollection"]
    features: list[EntityFeature]


class ObservationProperties(ApiModel):
    """The keys the observations route adds; stored observation keys pass through."""

    model_config = ConfigDict(extra="allow")

    entity_id: int
    source: str
    category: str
    status: str | None
    observed_at: IsoDateTime


class ObservationFeature(ApiModel):
    type: Literal["Feature"]
    geometry: dict[str, Any] | None
    properties: ObservationProperties


class ObservationFeatureCollection(ApiModel):
    """GET /timeseries/observations."""

    type: Literal["FeatureCollection"]
    features: list[ObservationFeature]
