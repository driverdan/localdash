"""Test doubles for the events feature."""
from __future__ import annotations

from app.events.geocoding import Coords, Geocoder
from app.events.sources.base import EventSource, RawEvent


class FakeGeocoder(Geocoder):
    """Geocoder that resolves from a fixed mapping and records its calls."""

    def __init__(self, mapping: dict[str, Coords] | None = None):
        self.mapping = mapping or {}
        self.calls: list[str] = []

    async def geocode(self, address: str) -> Coords | None:
        self.calls.append(address)
        return self.mapping.get(address)


class FakeSource(EventSource):
    """Source returning a fixed list of raw events."""

    def __init__(self, raws: list[RawEvent], name: str = "test-fake"):
        self.raws = raws
        self.name = name

    async def fetch(self) -> list[RawEvent]:
        return self.raws


class BrokenSource(EventSource):
    """Source whose fetch always fails."""

    name = "test-broken"

    async def fetch(self) -> list[RawEvent]:
        raise RuntimeError("feed down")
