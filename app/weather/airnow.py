"""Pure shaping of AirNow payloads into the weather response's `aqi` half.

No I/O here, mirroring nws.py: a pure function of a decoded airnowapi.org
JSON payload, testable offline against fixtures.
"""

from __future__ import annotations


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
    }
