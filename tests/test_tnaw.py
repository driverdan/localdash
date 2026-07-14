"""Tests for the Tennessee American Water advisory collector's normalize()."""

from __future__ import annotations

from app.collectors.tnaw import TnawCollector, _parse_layers
from app.config import Settings


def _collector() -> TnawCollector:
    return TnawCollector(Settings())


def _feature(**over):
    props = {
        "EventID": "130266",
        "EventNotificationType": "General",
        "EventType": "Planned Work",
        "EventState": "TN",
        "EventStatus": "Active",
        "EventHeader": "Chattanooga: Planned Water System Improvements : long text…",
        "EventHyperlink": "https://alertsdetail.awapps.com/alert/130266",
    }
    props.update(over.pop("props", {}))
    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[-85.3, 35.0], [-85.3, 35.1], [-85.2, 35.1], [-85.3, 35.0]]],
        },
        "properties": props,
        **over,
    }


def test_parse_layers():
    assert _parse_layers("17:emergency,16:general") == [
        ("17", "emergency"),
        ("16", "general"),
    ]


def test_basic_fields_and_stable_event_id():
    [obs] = _collector().normalize([("general", [_feature()])])
    # external_id is the feed's stable EventID (no lat/lon derivation).
    assert obs.external_id == "130266"
    assert obs.category == "general"
    assert obs.label.startswith("Chattanooga: Planned Water System Improvements")
    # status is EventType, exposed under the canonical key for dedup + the frontend.
    assert obs.status == "Planned Work"
    assert obs.properties["status"] == "Planned Work"
    assert obs.properties["advisory_type"] == "general"
    # Polygon geometry is carried through verbatim.
    assert obs.geometry["type"] == "Polygon"
    assert obs.lat is None and obs.lon is None
    assert obs.source_time is None


def test_emergency_and_general_categories_from_layers():
    out = _collector().normalize(
        [
            ("emergency", [_feature(props={"EventID": "1"})]),
            ("general", [_feature(props={"EventID": "2"})]),
        ]
    )
    by_cat = {o.category: o for o in out}
    assert set(by_cat) == {"emergency", "general"}


def test_features_without_id_or_geometry_are_dropped():
    out = _collector().normalize(
        [
            (
                "general",
                [
                    _feature(props={"EventID": None}),
                    {"type": "Feature", "geometry": None, "properties": {"EventID": "9"}},
                    _feature(props={"EventID": "ok"}),
                ],
            )
        ]
    )
    assert [o.external_id for o in out] == ["ok"]


def test_non_list_payload_is_empty():
    assert _collector().normalize({"not": "a list"}) == []
    assert _collector().normalize([("general", "not a list")]) == []
