"""Tests for the EPB outage collector's normalize() (pure, no network)."""

from __future__ import annotations

import httpx
import pytest

from app.collectors.epb import EpbCollector
from app.config import Settings


def _collector() -> EpbCollector:
    return EpbCollector(Settings())


def _incident(**over):
    item = {
        "customer_quantity": 123,
        "incident_status": "OUTAGE_REPORTED",
        "latitude": 35.022620,
        "longitude": -85.444421,
    }
    item.update(over)
    return item


def test_basic_fields_and_location_key():
    [obs] = _collector().normalize({"energy": [_incident()]})
    # No per-incident id in the feed: external_id is service + rounded location.
    assert obs.external_id == "energy:35.022620,-85.444421"
    assert obs.category == "energy"
    assert obs.label == "Energy Outage"
    assert obs.status == "OUTAGE_REPORTED"
    assert obs.lat == 35.022620 and obs.lon == -85.444421
    # The collector sets only obs.status; ingest records it on the entity.
    assert "status" not in obs.properties
    assert obs.properties["service"] == "energy"
    assert obs.source_time is None


def test_energy_and_fiber_categories_are_distinct():
    out = _collector().normalize(
        {"energy": [_incident()], "fiber": [_incident(customer_quantity=1)]}
    )
    by_cat = {o.category: o for o in out}
    assert set(by_cat) == {"energy", "fiber"}
    # Same coordinates but different service -> distinct entities (no collision).
    assert by_cat["energy"].external_id != by_cat["fiber"].external_id
    assert by_cat["fiber"].label == "Fiber Outage"


def test_missing_coordinates_are_dropped():
    out = _collector().normalize(
        {"energy": [_incident(latitude=None), _incident(longitude=None), _incident()]}
    )
    assert len(out) == 1


def test_same_location_collapses_to_one_entity():
    # Two incidents at the same point within a service share one entity key.
    out = _collector().normalize({"energy": [_incident(), _incident(customer_quantity=5)]})
    assert len(out) == 1


def test_non_dict_payload_is_empty():
    assert _collector().normalize([{"not": "a dict-keyed-by-service"}]) == []
    assert _collector().normalize({"energy": "not a list"}) == []


# --- fetch() (through the mock_http fixture) ---


async def test_fetch_requests_each_service_and_keys_incidents_by_it(mock_http):
    collector = _collector()

    def handler(request: httpx.Request) -> httpx.Response:
        service = request.url.path.split("/")[-2]
        if service == "fiber":
            return httpx.Response(200, json={"unexpected": True})  # no incidents list
        return httpx.Response(200, json={"incidents": [_incident()]})

    mock_http.install(handler)

    raw = await collector.fetch()

    assert [str(r.url) for r in mock_http.requests] == [
        f"{collector.base_url}/{s}/incidents" for s in collector.services
    ]
    assert raw == {"energy": [_incident()], "fiber": []}
    assert len(collector.normalize(raw)) == 1


async def test_fetch_non_2xx_raises(mock_http):
    mock_http.install(lambda request: httpx.Response(502))

    with pytest.raises(httpx.HTTPStatusError):
        await _collector().fetch()
