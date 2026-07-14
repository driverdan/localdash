"""Tests for the EPB outage collector's normalize() (pure, no network)."""

from __future__ import annotations

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
    # status is exposed under the canonical key for ingest dedup + the frontend.
    assert obs.properties["status"] == "OUTAGE_REPORTED"
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
