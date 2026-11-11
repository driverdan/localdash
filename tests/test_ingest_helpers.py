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


# Exact stored fingerprints. entities.geom_fingerprint persists these strings
# between polls, so any change to them makes every entity look moved once.


def test_point_fingerprint_pinned_exact_string():
    obs = _obs(lat=35.0451234567, lon=-85.3097654321)
    assert geom_fingerprint(obs) == "-85.309765,35.045123"


def test_polygon_fingerprint_pinned_exact_string():
    ring = [[-85.0, 35.0], [-85.0, 35.1], [-84.9, 35.1], [-85.0, 35.0]]
    obs = _obs(geometry=_poly(ring))
    assert geom_fingerprint(obs) == "1e3c7f63daf4a510065e511d7c370ed1ef8ca025"


def test_multipolygon_fingerprint_pinned_exact_string():
    ring = [[-85.0, 35.0], [-85.0, 35.1], [-84.9, 35.1], [-85.0, 35.0]]
    obs = _obs(geometry={"type": "MultiPolygon", "coordinates": [[ring]]})
    assert geom_fingerprint(obs) == "37addbf384b68e32171b98a9a9d0eb47188c1e41"


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


def test_geometry_point_fingerprints_like_lat_lon():
    via_geometry = _obs(geometry={"type": "Point", "coordinates": [-85.31, 35.04]})
    assert geom_fingerprint(via_geometry) == geom_fingerprint(_obs(lat=35.04, lon=-85.31))
    assert geom_fingerprint(via_geometry) == "-85.310000,35.040000"


def test_3d_point_uses_hashed_form_and_tracks_z():
    low = geom_fingerprint(_obs(geometry={"type": "Point", "coordinates": [-85.31, 35.04, 200]}))
    high = geom_fingerprint(_obs(geometry={"type": "Point", "coordinates": [-85.31, 35.04, 250]}))
    assert "," not in low  # sha1 hex, not the "lon,lat" form
    assert len(low) == 40
    assert low != high


# --- NormalizedObservation.resolved_geometry ---------------------------------------


def test_resolved_geometry_from_lat_lon_is_lon_lat_point():
    assert _obs(lat=35.04, lon=-85.31).resolved_geometry == {
        "type": "Point",
        "coordinates": [-85.31, 35.04],
    }


def test_resolved_geometry_explicit_geometry_wins():
    ring = [[-85.0, 35.0], [-85.0, 35.1], [-84.9, 35.1], [-85.0, 35.0]]
    obs = _obs(lat=35.04, lon=-85.31, geometry=_poly(ring))
    assert obs.resolved_geometry == _poly(ring)


def test_resolved_geometry_none_when_one_coordinate_missing():
    assert _obs(lat=35.0).resolved_geometry is None
    assert _obs(lon=-85.0).resolved_geometry is None


def test_resolved_geometry_none_when_nothing_set():
    assert _obs().resolved_geometry is None


def test_resolved_geometry_not_in_model_dump():
    assert "resolved_geometry" not in _obs(lat=35.04, lon=-85.31).model_dump()
