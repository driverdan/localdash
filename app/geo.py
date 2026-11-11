"""Geometry helpers for database writes."""

from __future__ import annotations


def ewkt_point(lat: float, lon: float) -> str:
    """EWKT for a PostGIS point from (lat, lon); WKT itself is (lon lat)."""
    return f"SRID=4326;POINT({lon} {lat})"
