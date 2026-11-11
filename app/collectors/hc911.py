"""Hamilton County, TN active-911 collector.

Reverse-engineered from https://www.hamiltontn911.gov/active-incidents.php
(js/map.js). The page calls a JSON endpoint every 60s with two custom headers
and renders the array on a Leaflet map. The endpoint returns a *snapshot* of
currently-active calls, so the time-series is built by polling + the ingest
service tracking each incident by master_incident_id over time.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.collectors.base import BaseCollector, NormalizedObservation, as_float
from app.config import Settings
from app.http import make_client
from app.timeutil import parse_iso_utc

# Calls with this type are filtered out by the source site (permitted burns).
EXCLUDED_TYPES = {"PERBURN"}


def _parse_dt(value: Any) -> datetime | None:
    # Values without an offset are read as UTC (the feed always sends "Z").
    dt = parse_iso_utc(value)
    # The feed uses 1900-01-01 as a "no value" sentinel for statusdatetime.
    return None if dt is None or dt.year < 1990 else dt


class HC911Collector(BaseCollector):
    source_key = "hc911"
    name = "Hamilton County TN 911"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.poll_interval = settings.hc911_poll_interval

    async def fetch(self) -> Any:
        headers = {
            "Content-Type": "application/json",
            "X-Frontend-Auth": self.settings.hc911_auth_token,
            "Origin": self.settings.hc911_origin,
        }
        async with make_client(timeout=30, follow_redirects=False) as client:
            resp = await client.get(self.settings.hc911_api_url, headers=headers)
            resp.raise_for_status()
            return resp.json()

    def normalize(self, raw: Any) -> list[NormalizedObservation]:
        if not isinstance(raw, list):
            return []

        out: list[NormalizedObservation] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            if item.get("type") in EXCLUDED_TYPES:
                continue

            external_id = item.get("master_incident_id")
            if external_id is None:
                continue

            # Category drives map icon / filtering, mirroring map.js getDepartment().
            agency = (item.get("agency_type") or "").strip()
            category = {"Law": "police", "Fire": "fire", "EMS": "ems"}.get(agency, "other")

            lat = as_float(item.get("latitude"))
            lon = as_float(item.get("longitude"))

            label = item.get("type") or item.get("type_description")
            source_time = _parse_dt(item.get("statusdatetime")) or _parse_dt(item.get("creation"))

            out.append(
                NormalizedObservation(
                    external_id=str(external_id),
                    category=category,
                    label=label,
                    lat=lat,
                    lon=lon,
                    status=item.get("status"),
                    source_time=source_time,
                    properties=item,
                )
            )
        return out
