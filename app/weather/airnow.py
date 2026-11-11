"""Pure shaping of AirNow payloads into the weather response's `aqi` half.

No I/O here, mirroring nws.py: pure functions of a decoded airnowapi.org JSON
payload (the /aq/observation/current/ziplatlong/ service), testable offline
against fixtures.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.weather.schemas import AirQuality

# AirNow's localTimeZone is a standard-time US abbreviation returned year-round
# (e.g. "EST" even during daylight saving), so map the ones it emits to fixed
# UTC offsets. Daylight variants are included defensively though AirNow does not
# normally send them. An unlisted zone leaves observed_at naive (display-only);
# the service then bounds staleness by fetch time instead.
_TZ_OFFSETS = {
    "EST": -5,
    "EDT": -4,
    "CST": -6,
    "CDT": -5,
    "MST": -7,
    "MDT": -6,
    "PST": -8,
    "PDT": -7,
    "AKST": -9,
    "AKDT": -8,
    "HST": -10,
    "HADT": -9,
    "HAST": -10,
}

# EPA AQI category upper bounds: 0-50 Good (1), 51-100 Moderate (2), 101-150
# USG (3), 151-200 Unhealthy (4), 201-300 Very Unhealthy (5), above 300
# Hazardous (6). Upper bounds rather than ranges so non-integer values land in
# the right category.
_CATEGORY_UPPER_BOUNDS = (50, 100, 150, 200, 300)


def aqi_category(value: float) -> int:
    """AQI value -> EPA category number (1-6).

    The ziplatlong service reports only a category name, but the chip's colors
    key off the number, so derive it from the value with the fixed EPA scale.
    """
    for number, upper in enumerate(_CATEGORY_UPPER_BOUNDS, start=1):
        if value <= upper:
            return number
    return len(_CATEGORY_UPPER_BOUNDS) + 1


def airnow_error_messages(payload: object) -> list[str]:
    """Message strings of an AirNow `{"WebServiceError": [...]}` envelope.

    AirNow answers with this envelope instead of observations both on errors
    (4xx/410, e.g. a retired service or a bad key) and on HTTP 200 when no
    monitor has data. Anything that is not the envelope yields [].
    """
    if not isinstance(payload, dict):
        return []
    errors = payload.get("WebServiceError")
    if not isinstance(errors, list):
        return []
    return [
        e["Message"] for e in errors if isinstance(e, dict) and isinstance(e.get("Message"), str)
    ]


def _hour(value: object) -> int | None:
    """AirNow hourObserved ("22:00"; a bare int is tolerated) -> hour 0-23."""
    if isinstance(value, int) and not isinstance(value, bool):
        hour = value
    elif isinstance(value, str):
        try:
            hour = int(value.strip().split(":", 1)[0])
        except ValueError:
            return None
    else:
        return None
    return hour if 0 <= hour <= 23 else None


def _observed_at(entry: dict) -> str | None:
    """AirNow dateObserved + hourObserved (local) + localTimeZone -> ISO-8601.

    The observation is hour-resolution (AirNow reports one reading per hour), so
    minutes are zeroed. A known localTimeZone yields a tz-aware timestamp; an
    unknown one yields a naive local timestamp for display only.
    """
    date = entry.get("dateObserved")
    hour = _hour(entry.get("hourObserved"))
    if not isinstance(date, str) or hour is None:
        return None
    try:
        base = datetime.strptime(date.strip(), "%Y-%m-%d")
    except ValueError:
        return None
    offset = _TZ_OFFSETS.get(str(entry.get("localTimeZone", "")).strip().upper())
    if offset is None:
        return base.replace(hour=hour).isoformat()
    return base.replace(hour=hour, tzinfo=timezone(timedelta(hours=offset))).isoformat()


def _aqi_value(entry: object) -> float | None:
    """An entry's usable nowcastAQI, or None (missing, non-numeric, -999 sentinel)."""
    if not isinstance(entry, dict):
        return None
    value = entry.get("nowcastAQI")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return None
    return value


def parse_airnow(payload: object) -> AirQuality | None:
    """Current-observations payload -> overall AQI, or None if unusable.

    AirNow reports one entry per pollutant (OZONE, PM2.5, PM10, ...); the
    overall AQI is the worst pollutant's value (the EPA convention — that
    pollutant is the "primary" one). Entries without a usable nowcastAQI are
    skipped; no usable entry, or a non-list payload (the WebServiceError
    envelope), means no AQI. Pollutant and category names pass through verbatim;
    the category number is derived from the value.
    """
    if not isinstance(payload, list):
        return None
    best: dict | None = None
    best_value: float | None = None
    for entry in payload:
        value = _aqi_value(entry)
        if value is None:
            continue
        if best_value is None or value > best_value:
            best, best_value = entry, value
    if best is None or best_value is None:
        return None
    return AirQuality(
        value=best_value,
        category=aqi_category(best_value),
        category_name=best.get("aqiCategoryName"),
        pollutant=best.get("parameterName"),
        observed_at=_observed_at(best),
    )
