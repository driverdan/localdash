"""Unit tests for the GeoJSON serialization helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from app.geojson import entity_properties, feature_collection, feature_geom


def test_feature_collection_wraps_features():
    point = {"type": "Point", "coordinates": [1.0, 2.0]}
    fc = feature_collection(iter([feature_geom(point, {})]))
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
