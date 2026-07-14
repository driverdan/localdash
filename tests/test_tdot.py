"""Tests for the TDOT SmartWay collector's normalize() (pure, no network)."""

from __future__ import annotations

from datetime import timezone

from app.collectors.tdot import TdotCollector
from app.config import Settings


def _collector() -> TdotCollector:
    return TdotCollector(Settings())


def _event(**over):
    item = {
        "id": 1,
        "status": "Unresolved",
        "eventTypeName": "Incident",
        "eventSubTypeDescription": "Congestion",
        "description": "I-24 EB near MM 182",
        "revisedDate": "2026-06-13T09:42:42.34-05:00",
        "isSevere": False,
        "locations": [
            {"midPoint": {"lat": 35.019349, "lng": -85.266656}, "countyName": "Hamilton"}
        ],
    }
    item.update(over)
    return item


def test_basic_fields_and_midpoint():
    [obs] = _collector().normalize([_event()])
    assert obs.external_id == "1"
    assert obs.category == "incident"
    assert obs.label == "Congestion"
    assert obs.status == "Unresolved"
    assert obs.lat == 35.019349 and obs.lon == -85.266656
    # revisedDate is Central (-05:00) and is normalized to UTC.
    assert obs.source_time.tzinfo == timezone.utc
    assert obs.source_time.hour == 14


def test_category_mapping():
    norm = _collector().normalize
    assert norm([_event(eventTypeName="Operations")])[0].category == "construction"
    assert norm([_event(eventTypeName="SpecialEvent")])[0].category == "special_event"
    assert norm([_event(eventTypeName="Mystery")])[0].category == "other"


def test_is_severe_overrides_category():
    [obs] = _collector().normalize([_event(eventTypeName="Incident", isSevere=True)])
    assert obs.category == "severe"


def test_dedupe_severe_wins_regardless_of_order():
    plain = _event(id=7, isSevere=False)
    severe = _event(id=7, isSevere=True)
    for batch in ([plain, severe], [severe, plain]):
        out = _collector().normalize(batch)
        assert len(out) == 1
        assert out[0].category == "severe"


def test_label_falls_back_to_event_type():
    [obs] = _collector().normalize([_event(eventSubTypeDescription=None)])
    assert obs.label == "Incident"


def test_missing_id_and_location_are_handled():
    out = _collector().normalize(
        [
            _event(id=None),  # dropped (no external_id)
            _event(id=9, locations=[]),  # kept, no coordinates
        ]
    )
    assert [o.external_id for o in out] == ["9"]
    assert out[0].lat is None and out[0].lon is None


def test_non_list_payload_is_empty():
    assert _collector().normalize({"not": "a list"}) == []
