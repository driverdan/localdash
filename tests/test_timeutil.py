"""Tests for the shared time helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.timeutil import as_utc, parse_iso_utc

UTC = UTC
EASTERN = ZoneInfo("America/New_York")


# --- as_utc ---


def test_as_utc_converts_an_aware_non_utc_value():
    value = datetime(2026, 1, 10, 13, 0, tzinfo=timezone(timedelta(hours=-5)))
    result = as_utc(value)
    assert result == datetime(2026, 1, 10, 18, 0, tzinfo=UTC)
    assert result.tzinfo is UTC


def test_as_utc_reads_a_naive_value_as_utc_by_default():
    assert as_utc(datetime(2026, 1, 10, 18, 0)) == datetime(2026, 1, 10, 18, 0, tzinfo=UTC)


def test_as_utc_reads_a_naive_value_in_the_given_zone():
    result = as_utc(datetime(2026, 1, 10, 18, 0), naive_tz=EASTERN)
    assert result == datetime(2026, 1, 10, 23, 0, tzinfo=UTC)
    assert result.tzinfo is UTC


# --- parse_iso_utc ---


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-01-10T18:00:00Z", datetime(2026, 1, 10, 18, 0, tzinfo=UTC)),
        ("2026-01-10T18:00:00+00:00", datetime(2026, 1, 10, 18, 0, tzinfo=UTC)),
        ("2026-01-10T13:00:00-05:00", datetime(2026, 1, 10, 18, 0, tzinfo=UTC)),
        ("2026-01-10T18:00:00", datetime(2026, 1, 10, 18, 0, tzinfo=UTC)),
        ("2026-01-10 18:00:00", datetime(2026, 1, 10, 18, 0, tzinfo=UTC)),
    ],
)
def test_parse_iso_utc_default_zone(value, expected):
    result = parse_iso_utc(value)
    assert result == expected
    assert result.tzinfo is UTC


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        # Winter: EST is UTC-5.
        ("2026-01-10T18:00:00", datetime(2026, 1, 10, 23, 0, tzinfo=UTC)),
        # Summer: EDT is UTC-4.
        ("2026-07-10T18:00:00", datetime(2026, 7, 10, 22, 0, tzinfo=UTC)),
        # An explicit offset wins over the naive-value zone.
        ("2026-07-10T18:00:00Z", datetime(2026, 7, 10, 18, 0, tzinfo=UTC)),
    ],
)
def test_parse_iso_utc_naive_values_use_the_given_zone(value, expected):
    assert parse_iso_utc(value, naive_tz=EASTERN) == expected


@pytest.mark.parametrize("value", ["", None, 12345, "not-a-date"])
def test_parse_iso_utc_returns_none_for_unparseable_input(value):
    assert parse_iso_utc(value) is None
    assert parse_iso_utc(value, naive_tz=EASTERN) is None
