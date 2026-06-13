"""Unit tests for the HC911 collector's parsing helpers."""
from __future__ import annotations

from app.collectors.hc911 import _as_float, _parse_dt


def test_parse_dt_iso_with_z():
    dt = _parse_dt("2026-06-13T15:14:25.000Z")
    assert dt is not None
    assert (dt.year, dt.month, dt.day) == (2026, 6, 13)
    assert dt.tzinfo is not None  # tz-aware (UTC)


def test_parse_dt_rejects_1900_sentinel():
    assert _parse_dt("1900-01-01T00:00:00.000Z") is None


def test_parse_dt_handles_bad_input():
    assert _parse_dt("") is None
    assert _parse_dt(None) is None
    assert _parse_dt("not-a-date") is None
    assert _parse_dt(12345) is None


def test_as_float_valid():
    assert _as_float("35.04") == 35.04
    assert _as_float(35) == 35.0


def test_as_float_invalid_returns_none():
    assert _as_float(None) is None
    assert _as_float("x") is None
    assert _as_float("nan") is None  # NaN rejected
    assert _as_float(float("nan")) is None
