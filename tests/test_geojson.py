"""Unit tests for the GeoJSON serialization helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from app.geojson import entity_properties, feature, feature_collection, feature_geom


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


def test_feature_geom_wraps_polygon():
    geom = {"type": "Polygon", "coordinates": [[[0, 0], [0, 1], [1, 1], [0, 0]]]}
    f = feature_geom(geom, {"a": 1}, fid=3)
    assert f["geometry"] == geom
    assert f["properties"] == {"a": 1}
    assert f["id"] == 3


def test_feature_geom_allows_null_geometry():
    assert feature_geom(None, {})["geometry"] is None


def test_entity_properties_authoritative_keys_override_raw():
    seen = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)
    props = entity_properties(
        {"id": "upstream-99", "source": "raw", "extra": 1, "status": "raw"},
        id=7,
        source="hc911",
        external_id="abc",
        category="police",
        label="Test",
        last_seen_at=seen,
        active=True,
        status="Enroute",
    )
    assert props["id"] == 7
    assert props["source"] == "hc911"
    assert props["status"] == "Enroute"
    assert props["extra"] == 1  # raw fields pass through
    assert props["last_seen_at"] == seen.isoformat()
    assert props["active"] is True


def test_entity_properties_tolerates_missing_raw_and_timestamp():
    props = entity_properties(
        None,
        id=1,
        source="s",
        external_id="e",
        category=None,
        label=None,
        last_seen_at=None,
        active=False,
        status="Closed",
    )
    assert props["last_seen_at"] is None
    assert props["active"] is False
