"""Tests for the shared geometry helpers."""

from app.geo import ewkt_point


def test_ewkt_point_writes_lon_before_lat():
    assert ewkt_point(35.04, -85.31) == "SRID=4326;POINT(-85.31 35.04)"
