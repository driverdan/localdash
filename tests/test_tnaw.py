"""Tests for the Tennessee American Water advisory collector's normalize()."""

from __future__ import annotations

import httpx
import pytest

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
    # status is EventType; the collector sets only obs.status and ingest records it.
    assert obs.status == "Planned Work"
    assert "status" not in obs.properties
    assert obs.properties["advisory_type"] == "general"
    # Polygon geometry is carried through verbatim.
    assert obs.geometry["type"] == "Polygon"
    assert obs.lat is None and obs.lon is None
    # Ingest reads resolved_geometry, which is the feature's polygon unchanged.
    assert obs.resolved_geometry == _feature()["geometry"]
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


# --- fetch() (through the mock_http fixture) ---


async def test_fetch_queries_each_layer_filtered_to_the_state(mock_http):
    collector = _collector()

    def handler(request: httpx.Request) -> httpx.Response:
        layer = request.url.path.split("/")[-2]
        return httpx.Response(200, json={"features": [_feature(props={"EventID": layer})]})

    mock_http.install(handler)

    raw = await collector.fetch()

    layers = [layer for layer, _ in collector.layers]
    assert [r.url.path.split("/")[-2] for r in mock_http.requests] == layers
    for request in mock_http.requests:
        assert request.url.path.endswith("/query")
        assert request.url.params["where"] == f"EventState='{collector.state}'"
        assert request.url.params["f"] == "geojson"
        assert request.url.params["outSR"] == "4326"
    assert [category for category, _ in raw] == [c for _, c in collector.layers]
    assert len(collector.normalize(raw)) == len(layers)


async def test_fetch_non_2xx_raises(mock_http):
    mock_http.install(lambda request: httpx.Response(500))

    with pytest.raises(httpx.HTTPStatusError):
        await _collector().fetch()
