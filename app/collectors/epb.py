"""EPB (Chattanooga) electric + fiber outage collector.

Reverse-engineered from https://epb.com/outage-storm-center/ (see docs/epb-outage-api.md).
The page's "Automated Grid" map (component `c7100`) loads its data through a small client
gateway (`repository/outages.js` -> `backends/gateway.js`) that resolves to a public JSON
API at `https://api.epb.com`. Two unauthenticated endpoints back the map markers:

    GET {base}/energy/incidents   -> {"incidents": [...]}   active power outages
    GET {base}/fiber/incidents    -> {"incidents": [...]}   active fiber outages

(There are sibling `/restores` endpoints, but they are just the last 24h of *restored*
locations with no status or stable id — redundant here, because LocalDash already records
restoration via the ingest closure sweep when an incident drops out of the snapshot.)

Each incident is bare: `{customer_quantity, incident_status, latitude, longitude}` with **no
id of its own**. Like hc911/tdot this is a snapshot of currently-active outages, so LocalDash
builds the time-series itself by polling. The stable entity key is the outage's *location*
(an outage sits at a fixed point — a feeder/transformer — while its `incident_status`
progresses OUTAGE_REPORTED -> EN_ROUTE -> REPAIR_IN_PROGRESS and then disappears once
restored), so `external_id` is derived from the rounded lat/lon, scoped by service.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.collectors.base import BaseCollector, NormalizedObservation
from app.config import Settings

# service -> human label shown as the marker's title.
_SERVICE_LABEL = {"energy": "Energy Outage", "fiber": "Fiber Outage"}


class EpbCollector(BaseCollector):
    source_key = "epb"
    name = "EPB Outages"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.poll_interval = settings.epb_poll_interval
        self.base_url = settings.epb_api_base_url.rstrip("/")
        self.services = [s.strip() for s in settings.epb_services.split(",") if s.strip()]

    async def fetch(self) -> Any:
        headers = {"Accept": "application/json", "User-Agent": self.settings.user_agent}
        out: dict[str, list] = {}
        async with httpx.AsyncClient(timeout=30) as client:
            for service in self.services:
                resp = await client.get(f"{self.base_url}/{service}/incidents", headers=headers)
                resp.raise_for_status()
                payload = resp.json()
                incidents = payload.get("incidents") if isinstance(payload, dict) else None
                out[service] = incidents if isinstance(incidents, list) else []
        return out

    def normalize(self, raw: Any) -> list[NormalizedObservation]:
        if not isinstance(raw, dict):
            return []

        by_id: dict[str, NormalizedObservation] = {}
        for service, incidents in raw.items():
            if not isinstance(incidents, list):
                continue
            for item in incidents:
                if not isinstance(item, dict):
                    continue
                lat = _as_float(item.get("latitude"))
                lon = _as_float(item.get("longitude"))
                if lat is None or lon is None:
                    continue

                # The feed has no per-incident id; an outage's location is its identity.
                external_id = f"{service}:{lat:.6f},{lon:.6f}"
                by_id[external_id] = NormalizedObservation(
                    external_id=external_id,
                    category=service,  # "energy" | "fiber"
                    label=_SERVICE_LABEL.get(service, "Outage"),
                    lat=lat,
                    lon=lon,
                    status=item.get("incident_status"),
                    # The feed carries no timestamp; observed_at (poll time) is the series clock.
                    source_time=None,
                    # Expose the incident status under the canonical `status` key (the feed
                    # calls it `incident_status`); ingest's state-change dedup and the frontend
                    # both read `properties["status"]`.
                    properties={**item, "service": service, "status": item.get("incident_status")},
                )
        return list(by_id.values())


def _as_float(value: Any) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if f == f else None  # reject NaN
