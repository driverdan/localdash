"""Response models for the weather API (/api/v1/weather/current).

Fields are declared in the order the JSON has always carried them; see
app/contracts.py for the shared base model. Numbers passed through from NWS or
AirNow are `int | float` so an integer stays an integer on the wire. The
`observed_at` fields stay strings: NWS's is its own string, passed through, and
AirNow's may be a naive local time (see airnow.py), so neither is reparsed.
"""

from __future__ import annotations

from app.contracts import ApiModel


class CurrentConditions(ApiModel):
    temperature_f: int
    description: str
    icon: str | None
    wind_mph: int | None
    wind_direction: str | None
    humidity_percent: int | None
    observed_at: str | None


class ForecastPeriod(ApiModel):
    name: str
    temperature: int | float
    temperature_unit: str
    precip_percent: int | float | None
    short_forecast: str
    detailed_forecast: str


class AirQuality(ApiModel):
    value: int | float
    category: int
    category_name: str | None
    pollutant: str | None
    observed_at: str | None


class WeatherPayload(ApiModel):
    current: CurrentConditions | None
    periods: list[ForecastPeriod]
    aqi: AirQuality | None
