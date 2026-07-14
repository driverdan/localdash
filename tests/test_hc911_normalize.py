"""Offline tests for the HC911 collector's normalize() — no network, no DB."""

from __future__ import annotations

from app.collectors.hc911 import HC911Collector


def test_normalize_maps_core_fields(settings, hc911_payload):
    collector = HC911Collector(settings)
    obs = collector.normalize(hc911_payload)

    # Every non-PERBURN record with a master_incident_id should map.
    expected = [
        r
        for r in hc911_payload
        if r.get("type") != "PERBURN" and r.get("master_incident_id") is not None
    ]
    assert len(obs) == len(expected)

    first = obs[0]
    assert first.external_id  # stringified master_incident_id
    assert first.category in {"police", "fire", "ems", "other"}
    assert first.status is not None
    assert first.properties  # full original record preserved


def test_normalize_filters_perburn():
    collector = HC911Collector(_DummySettings())
    raw = [
        {
            "master_incident_id": 1,
            "type": "PERBURN",
            "agency_type": "Fire",
            "latitude": 35.0,
            "longitude": -85.0,
            "status": "Queued",
        },
        {
            "master_incident_id": 2,
            "type": "Property",
            "agency_type": "Law",
            "latitude": 35.0,
            "longitude": -85.0,
            "status": "Queued",
        },
    ]
    obs = collector.normalize(raw)
    assert [o.external_id for o in obs] == ["2"]
    assert obs[0].category == "police"


def test_normalize_handles_bad_coords_and_sentinel_time():
    collector = HC911Collector(_DummySettings())
    raw = [
        {
            "master_incident_id": 9,
            "type": "MVC",
            "agency_type": "EMS",
            "latitude": "not-a-number",
            "longitude": None,
            "status": "Enroute",
            "statusdatetime": "1900-01-01T00:00:00.000Z",
            "creation": "2026-06-13T15:14:25.000Z",
        }
    ]
    obs = collector.normalize(raw)
    assert len(obs) == 1
    o = obs[0]
    assert o.lat is None and o.lon is None
    assert o.category == "ems"
    # 1900 sentinel rejected; falls back to creation.
    assert o.source_time is not None and o.source_time.year == 2026


class _DummySettings:
    hc911_api_url = "http://example"
    hc911_auth_token = "t"
    hc911_origin = "o"
    hc911_poll_interval = 60
    user_agent = "test"
