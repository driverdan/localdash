"""Unit tests for ingest geometry helpers (DB-free).

The `state_changed` rule and the full DB lifecycle live in test_ingest.py.
"""

from __future__ import annotations

from app.collectors.base import NormalizedObservation
from app.ingest import geom_fingerprint


def _obs(**kw) -> NormalizedObservation:
    return NormalizedObservation(external_id="x", **kw)


def test_point_fingerprint_is_lon_lat_6dp():
    assert geom_fingerprint(_obs(lat=35.04, lon=-85.31)) == "-85.310000,35.040000"


def test_point_fingerprint_none_when_coord_missing():
    assert geom_fingerprint(_obs(lat=35.0)) is None
    assert geom_fingerprint(_obs(lon=-85.0)) is None
    assert geom_fingerprint(_obs()) is None


def test_point_sub_threshold_jitter_same_fingerprint():
    # ~0.1 m jitter rounds away -> identical fingerprint (preserves prior behavior).
    a = geom_fingerprint(_obs(lat=35.0, lon=-85.0))
    b = geom_fingerprint(_obs(lat=35.0 + 1e-9, lon=-85.0))
    assert a == b


def test_point_above_threshold_move_differs():
    a = geom_fingerprint(_obs(lat=35.0, lon=-85.0))
    b = geom_fingerprint(_obs(lat=35.5, lon=-85.0))
    assert a != b


def _poly(*rings) -> dict:
    return {"type": "Polygon", "coordinates": list(rings)}


def test_polygon_fingerprint_is_stable():
    ring = [[-85.0, 35.0], [-85.0, 35.1], [-84.9, 35.1], [-85.0, 35.0]]
    assert geom_fingerprint(_obs(geometry=_poly(ring))) == geom_fingerprint(
        _obs(geometry=_poly(ring))
    )


def test_polygon_reshape_changes_fingerprint():
    ring_a = [[-85.0, 35.0], [-85.0, 35.1], [-84.9, 35.1], [-85.0, 35.0]]
    ring_b = [[-85.0, 35.0], [-85.0, 35.2], [-84.9, 35.2], [-85.0, 35.0]]
    assert geom_fingerprint(_obs(geometry=_poly(ring_a))) != geom_fingerprint(
        _obs(geometry=_poly(ring_b))
    )


def test_polygon_sub_threshold_jitter_same_fingerprint():
    ring = [[-85.0, 35.0], [-85.0, 35.1], [-84.9, 35.1], [-85.0, 35.0]]
    jitter = [[-85.0 + 1e-9, 35.0], [-85.0, 35.1], [-84.9, 35.1], [-85.0, 35.0]]
    assert geom_fingerprint(_obs(geometry=_poly(ring))) == geom_fingerprint(
        _obs(geometry=_poly(jitter))
    )
