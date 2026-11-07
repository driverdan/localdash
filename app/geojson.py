"""Helpers for emitting GeoJSON (RFC 7946) Features / FeatureCollections."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable


def feature(
    lon: float | None, lat: float | None, properties: dict[str, Any], fid: Any = None
) -> dict:
    geometry = None
    if lon is not None and lat is not None:
        geometry = {"type": "Point", "coordinates": [lon, lat]}
    return feature_geom(geometry, properties, fid=fid)


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
