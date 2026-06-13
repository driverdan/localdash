"""Helpers for emitting GeoJSON (RFC 7946) Features / FeatureCollections."""
from __future__ import annotations

from typing import Any, Iterable


def feature(lon: float | None, lat: float | None, properties: dict[str, Any], fid: Any = None) -> dict:
    geometry = None
    if lon is not None and lat is not None:
        geometry = {"type": "Point", "coordinates": [lon, lat]}
    feat: dict[str, Any] = {"type": "Feature", "geometry": geometry, "properties": properties}
    if fid is not None:
        feat["id"] = fid
    return feat


def feature_collection(features: Iterable[dict]) -> dict:
    return {"type": "FeatureCollection", "features": list(features)}
