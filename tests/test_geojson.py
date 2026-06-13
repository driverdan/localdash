"""Unit tests for the GeoJSON serialization helpers."""
from __future__ import annotations

from app.geojson import feature, feature_collection


def test_feature_with_point_geometry():
    f = feature(-85.31, 35.04, {"status": "Queued"}, fid=7)
    assert f["type"] == "Feature"
    assert f["geometry"] == {"type": "Point", "coordinates": [-85.31, 35.04]}
    assert f["properties"] == {"status": "Queued"}
    assert f["id"] == 7


def test_feature_without_coordinates_has_null_geometry():
    f = feature(None, None, {"a": 1})
    assert f["geometry"] is None
    assert "id" not in f  # fid omitted


def test_feature_missing_one_coordinate_is_null_geometry():
    assert feature(None, 35.0, {})["geometry"] is None
    assert feature(-85.0, None, {})["geometry"] is None


def test_feature_collection_wraps_features():
    fc = feature_collection(iter([feature(1.0, 2.0, {})]))
    assert fc["type"] == "FeatureCollection"
    assert isinstance(fc["features"], list)
    assert len(fc["features"]) == 1


def test_feature_collection_empty():
    assert feature_collection([]) == {"type": "FeatureCollection", "features": []}
