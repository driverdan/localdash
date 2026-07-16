"""TDOT SmartWay collector — Tennessee statewide roadway events.

Reverse-engineered from https://smartway.tn.gov/traffic (see docs/tdot-smartway-api.md).
The SmartWay Angular app loads a runtime config (`config.prod.json`) that hands every
browser an API base URL + a static app key, then calls one endpoint per map layer. Each
endpoint returns a *snapshot* of currently-active items with no history — so, exactly like
the hc911 source, LocalDash builds the time-series itself by polling and tracking each event
by its `id` over time (the ingest service handles status transitions + the closure sweep).

This collector covers the four event-style endpoints (incidents, construction/operations,
special events, severe-impact). They share one object schema and their `id`s come from a
single event system, so observations are merged into one source and de-duplicated by id (a
severe event also present in the incidents feed is kept once, with "severe" winning).
Cameras / message signs / rest areas are mostly-static infrastructure and are intentionally
excluded from this time-series source.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.collectors.base import BaseCollector, NormalizedObservation
from app.config import Settings

# eventTypeName -> our category. `isSevere` items override to "severe" (see _category).
_TYPE_CATEGORY = {
    "Incident": "incident",
    "Operations": "construction",
    "SpecialEvent": "special_event",
}


def _category(item: dict) -> str:
    if item.get("isSevere"):
        return "severe"
    return _TYPE_CATEGORY.get(item.get("eventTypeName"), "other")


def _parse_dt(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _midpoint(item: dict) -> tuple[float | None, float | None]:
    """(lat, lon) from the first location's midPoint, falling back to its first coordinate."""
    locations = item.get("locations")
    if not isinstance(locations, list) or not locations:
        return None, None
    loc = locations[0] or {}
    pt = loc.get("midPoint")
    if not isinstance(pt, dict):
        coords = loc.get("coordinates")
        pt = coords[0] if isinstance(coords, list) and coords else None
    if not isinstance(pt, dict):
        return None, None
    return _as_float(pt.get("lat")), _as_float(pt.get("lng"))


class TdotCollector(BaseCollector):
    source_key = "tdot"
    name = "TDOT SmartWay"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.poll_interval = settings.tdot_poll_interval
        self.base_url = settings.tdot_api_base_url.rstrip("/")
        self.api_key = settings.tdot_api_key
        self.endpoints = [e.strip() for e in settings.tdot_endpoints.split(",") if e.strip()]

    async def fetch(self) -> Any:
        headers = {"X-API-Key": self.api_key, "User-Agent": self.settings.user_agent}
        out: list[dict] = []
        async with httpx.AsyncClient(timeout=30) as client:
            for endpoint in self.endpoints:
                resp = await client.get(f"{self.base_url}/{endpoint}", headers=headers)
                if resp.status_code == 204:
                    continue  # endpoint active but currently empty (e.g. weather)
                resp.raise_for_status()
                payload = resp.json()
                if isinstance(payload, list):
                    out.extend(p for p in payload if isinstance(p, dict))
        return out

    def normalize(self, raw: Any) -> list[NormalizedObservation]:
        if not isinstance(raw, list):
            return []

        by_id: dict[str, NormalizedObservation] = {}
        for item in raw:
            if not isinstance(item, dict):
                continue
            ext = item.get("id")
            if ext is None:
                continue

            lat, lon = _midpoint(item)
            obs = NormalizedObservation(
                external_id=str(ext),
                category=_category(item),
                label=item.get("eventSubTypeDescription") or item.get("eventTypeName"),
                lat=lat,
                lon=lon,
                status=item.get("status"),
                source_time=_parse_dt(item.get("revisedDate"))
                or _parse_dt(item.get("beginningDate")),
                properties=item,
            )

            # De-dupe across endpoints; a severe duplicate wins over a plain one.
            prev = by_id.get(obs.external_id)
            if prev is None or (obs.category == "severe" and prev.category != "severe"):
                by_id[obs.external_id] = obs
        return list(by_id.values())


def _as_float(value: Any) -> float | None:
    try:
        f = float(value)
    except TypeError, ValueError:
        return None
    return f if f == f else None  # reject NaN
