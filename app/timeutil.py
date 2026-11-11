"""Shared time helpers: normalising datetimes and ISO-8601 strings to aware UTC."""

from __future__ import annotations

from datetime import datetime, timezone, tzinfo


def as_utc(value: datetime, naive_tz: tzinfo = timezone.utc) -> datetime:
    """Return ``value`` as an aware UTC datetime.

    A naive ``value`` is read as a wall-clock time in ``naive_tz`` (UTC by
    default); an aware one is converted to UTC.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=naive_tz)
    return value.astimezone(timezone.utc)


def parse_iso_utc(value: object, naive_tz: tzinfo = timezone.utc) -> datetime | None:
    """Parse an ISO-8601 string into an aware UTC datetime.

    Returns None for a falsy or non-string ``value`` and for a string that is
    not ISO-8601. A value without an offset is read as a wall-clock time in
    ``naive_tz`` (UTC by default).
    """
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return as_utc(parsed, naive_tz)
