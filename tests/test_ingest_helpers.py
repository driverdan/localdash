"""Unit tests for ingest geometry/movement helpers (DB-free).

The `state_changed` rule and the full DB lifecycle live in test_ingest.py.
"""

from __future__ import annotations

from app.ingest import _ewkt, _moved


def test_ewkt_builds_point_lon_lat_order():
    assert _ewkt(35.04, -85.31) == "SRID=4326;POINT(-85.31 35.04)"


def test_ewkt_none_when_coord_missing():
    assert _ewkt(None, -85.0) is None
    assert _ewkt(35.0, None) is None
    assert _ewkt(None, None) is None


def test_moved_both_none_is_false():
    assert _moved(None, None) is False


def test_moved_one_none_is_true():
    assert _moved(None, 35.0) is True
    assert _moved(35.0, None) is True


def test_moved_beyond_epsilon():
    assert _moved(35.0, 35.5) is True


def test_moved_sub_epsilon_is_false():
    assert _moved(35.0, 35.0 + 1e-7) is False
