"""API response models and the ingest Diff structure."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Diff:
    """Result of one ingest cycle, broadcast to WebSocket clients.

    `new` and `updated` carry GeoJSON Features for the affected entities;
    `closed` carries the entity ids that are no longer active.
    """

    source_key: str
    new: list[dict] = field(default_factory=list)
    updated: list[dict] = field(default_factory=list)
    closed: list[int] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (self.new or self.updated or self.closed)

    def to_message(self) -> dict[str, Any]:
        return {
            "type": "diff",
            "source": self.source_key,
            "new": self.new,
            "updated": self.updated,
            "closed": self.closed,
        }
