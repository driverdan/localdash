"""Tennessee American Water advisory collector (Chattanooga-area water).

Reverse-engineered from the public American Water **Customer Advisory Map** at
https://awgis.amwater.com/CustomerAdvisoryMap/ (see docs/tnaw-advisory-api.md). That
Esri Web AppBuilder app loads a public webmap whose operational layer is an
unauthenticated ArcGIS MapServer:

    {base}/{layer}/query?where=EventState='TN'&outFields=*&returnGeometry=true
                        &outSR=4326&f=geojson

The feed is national, so `EventState` filters it to Tennessee server-side. Two Active
advisory layers are polled (17 = Emergency, 16 = General); the Lifted layer (15) is not
ingested — a lifted advisory is one that left the Active layers, so LocalDash's ingest
closure sweep retires it automatically.

Unlike epb/hc911/tdot the features are **affected-area polygons**, not points, and each
carries a stable `EventID` — used directly as the entity's `external_id` (no lat/lon
derivation). Like the others this is a snapshot, so LocalDash builds the time-series by
polling: an advisory's `status`/geometry changing records a new observation, and its
disappearance closes it.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.collectors.base import BaseCollector, NormalizedObservation
from app.config import Settings


def _parse_layers(spec: str) -> list[tuple[str, str]]:
    """ "17:emergency,16:general" -> [("17","emergency"), ("16","general")]."""
    out: list[tuple[str, str]] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        layer, _, category = part.partition(":")
        out.append((layer.strip(), (category.strip() or "general")))
    return out


class TnawCollector(BaseCollector):
    source_key = "tnaw"
    name = "TN American Water Advisories"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.poll_interval = settings.tnaw_poll_interval
        self.base_url = settings.tnaw_api_base_url.rstrip("/")
        self.state = settings.tnaw_state
        self.layers = _parse_layers(settings.tnaw_layers)

    async def fetch(self) -> Any:
        headers = {"Accept": "application/json", "User-Agent": self.settings.user_agent}
        params = {
            "where": f"EventState='{self.state}'",
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "geojson",
        }
        out: list[tuple[str, list]] = []
        async with httpx.AsyncClient(timeout=30) as client:
            for layer, category in self.layers:
                resp = await client.get(
                    f"{self.base_url}/{layer}/query", params=params, headers=headers
                )
                resp.raise_for_status()
                payload = resp.json()
                features = payload.get("features") if isinstance(payload, dict) else None
                out.append((category, features if isinstance(features, list) else []))
        return out

    def normalize(self, raw: Any) -> list[NormalizedObservation]:
        if not isinstance(raw, list):
            return []

        # Keyed by EventID so the same advisory returned by more than one layer (or
        # poll) resolves to one entity; last write wins, Emergency layer polled first.
        by_id: dict[str, NormalizedObservation] = {}
        for category, features in raw:
            if not isinstance(features, list):
                continue
            for feat in features:
                if not isinstance(feat, dict):
                    continue
                props = feat.get("properties") or {}
                geometry = feat.get("geometry")
                event_id = props.get("EventID")
                if event_id is None or not isinstance(geometry, dict):
                    continue

                external_id = str(event_id)
                # EventType (Planned Work / Emergency Repair) is more informative on
                # the map than EventStatus (almost always "Active"); expose it as the
                # canonical status that ingest dedup and the frontend both read.
                status = props.get("EventType") or props.get("EventStatus")
                by_id[external_id] = NormalizedObservation(
                    external_id=external_id,
                    category=category,  # "emergency" | "general"
                    label=props.get("EventHeader"),
                    geometry=geometry,
                    status=status,
                    # The feed carries edit timestamps in properties; observed_at
                    # (poll time) remains the series clock.
                    source_time=None,
                    properties={**props, "advisory_type": category, "status": status},
                )
        return list(by_id.values())
