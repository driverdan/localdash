"""Pure shaping of AirNow payloads into the weather response's `aqi` half.

No I/O here, mirroring nws.py: a pure function of a decoded airnowapi.org
JSON payload, testable offline against fixtures.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

# AirNow's LocalTimeZone is a standard-time US abbreviation returned year-round
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


def _observed_at(entry: dict) -> str | None:
    """AirNow DateObserved + HourObserved (local) + LocalTimeZone -> ISO-8601.

    The observation is hour-resolution (AirNow reports one reading per hour), so
    minutes are zeroed. A known LocalTimeZone yields a tz-aware timestamp; an
    unknown one yields a naive local timestamp for display only.
    """
    date = entry.get("DateObserved")
    hour = entry.get("HourObserved")
    if not isinstance(date, str) or not isinstance(hour, int):
        return None
    try:
        base = datetime.strptime(date.strip(), "%Y-%m-%d")
    except ValueError:
        return None
    offset = _TZ_OFFSETS.get(str(entry.get("LocalTimeZone", "")).strip().upper())
    if offset is None:
        return base.replace(hour=hour).isoformat()
    return base.replace(hour=hour, tzinfo=timezone(timedelta(hours=offset))).isoformat()


def parse_airnow(payload: list) -> dict | None:
    """Current-observations payload -> overall AQI, or None if unusable.

    AirNow reports one entry per pollutant (O3, PM2.5, ...); the overall AQI
    is the worst pollutant's value (the EPA convention — that pollutant is the
    "primary" one). Missing or negative AQI values (AirNow uses -999
    sentinels) are skipped; no usable entry means no AQI.
    """
    best: dict | None = None
    for entry in payload:
        aqi = entry.get("AQI")
        if not isinstance(aqi, (int, float)) or aqi < 0:
            continue
        if best is None or aqi > best["AQI"]:
            best = entry
    if best is None:
        return None
    category = best.get("Category") or {}
    return {
        "value": best["AQI"],
        "category": category.get("Number"),
        "category_name": category.get("Name"),
        "pollutant": best.get("ParameterName"),
        "observed_at": _observed_at(best),
    }
