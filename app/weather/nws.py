"""Pure shaping of NWS payloads into the /api/v1/weather/current response.

No I/O here: every function is a pure function of a decoded api.weather.gov
JSON payload, so the whole module is testable offline against fixtures.
"""

from __future__ import annotations

# Points on a 16-wind compass rose, clockwise from north (22.5° apart).
_COMPASS = (
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
)  # fmt: skip


def _compass(degrees: float | None) -> str | None:
    if degrees is None:
        return None
    return _COMPASS[round(degrees / 22.5) % 16]


def _quantity(properties: dict, field: str) -> float | None:
    """Unwrap an NWS quantitative value ({unitCode, value}); value may be null."""
    return (properties.get(field) or {}).get("value")


def parse_points(payload: dict) -> tuple[str, str]:
    """Gridpoint discovery: /points/{lat},{lon} -> (forecast URL, stations URL)."""
    properties = payload["properties"]
    return properties["forecast"], properties["observationStations"]


def parse_stations(payload: dict, limit: int) -> list[str]:
    """Station-list payload -> the first `limit` station URLs (nearest first)."""
    return [feature["id"] for feature in payload.get("features", [])[:limit]]


def parse_forecast(payload: dict, count: int = 2) -> list[dict]:
    """Forecast payload -> the first `count` periods, names passed through verbatim.

    NWS renames the leading period through the day ("Today" -> "This
    Afternoon" -> "Tonight"), so the name is data, never synthesized.
    """
    return [
        {
            "name": period["name"],
            "temperature": period["temperature"],
            "temperature_unit": period["temperatureUnit"],
            "precip_percent": _quantity(period, "probabilityOfPrecipitation"),
            "short_forecast": period["shortForecast"],
            "detailed_forecast": period["detailedForecast"],
        }
        for period in payload["properties"]["periods"][:count]
    ]


def parse_observation(payload: dict) -> dict | None:
    """Latest-observation payload -> current conditions, or None if unusable.

    NWS observations report °C (and km/h wind); the response speaks °F/mph.
    Stations sometimes report a null temperature — that observation is
    unusable, and the caller falls back to the next station.
    """
    properties = payload["properties"]
    temp_c = _quantity(properties, "temperature")
    if temp_c is None:
        return None
    wind_kmh = _quantity(properties, "windSpeed")
    humidity = _quantity(properties, "relativeHumidity")
    return {
        "temperature_f": round(temp_c * 9 / 5 + 32),
        "description": properties.get("textDescription") or "",
        "icon": properties.get("icon"),
        "wind_mph": round(wind_kmh * 0.621371) if wind_kmh is not None else None,
        "wind_direction": _compass(_quantity(properties, "windDirection")),
        "humidity_percent": round(humidity) if humidity is not None else None,
        "observed_at": properties.get("timestamp"),
    }
