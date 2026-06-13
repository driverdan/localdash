"""Unit tests for the collector base classes."""
from __future__ import annotations

import pytest

from app.collectors.base import BaseCollector, NormalizedObservation


def test_normalized_observation_defaults():
    o = NormalizedObservation(external_id="42")
    assert o.external_id == "42"
    assert o.category == "default"
    assert o.properties == {}
    assert o.lat is None and o.lon is None
    assert o.status is None


def test_normalized_observation_requires_external_id():
    with pytest.raises(Exception):
        NormalizedObservation()  # type: ignore[call-arg]


def test_base_collector_is_abstract():
    with pytest.raises(TypeError):
        BaseCollector()  # type: ignore[abstract]


async def test_collect_pipes_fetch_into_normalize():
    seen = {}

    class DummyCollector(BaseCollector):
        source_key = "dummy"
        name = "Dummy"

        async def fetch(self):
            return [{"id": "a"}, {"id": "b"}]

        def normalize(self, raw):
            seen["raw"] = raw
            return [NormalizedObservation(external_id=r["id"]) for r in raw]

    result = await DummyCollector().collect()
    assert seen["raw"] == [{"id": "a"}, {"id": "b"}]
    assert [o.external_id for o in result] == ["a", "b"]
