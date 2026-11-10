"""Weather feature: NWS-proxied current conditions + today's forecast.

Mounted at /api/v1/weather (see app/main.py; registration is gated by the
weather_enabled setting).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.weather.schemas import WeatherPayload
from app.weather.service import service

router = APIRouter()


@router.get("/current", response_model=WeatherPayload)
async def get_current() -> WeatherPayload:
    """Current conditions + the leading forecast periods, cached per TTL."""
    try:
        return await service.get_current()
    except Exception as exc:  # cold cache and NWS unreachable
        raise HTTPException(status_code=502, detail="weather upstream unavailable") from exc
