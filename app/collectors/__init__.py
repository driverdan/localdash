"""Collector registry.

To add a new source: write a BaseCollector subclass in this package and append
an instance to the list returned by build_collectors(). Nothing else needs to
change — the scheduler, ingestion service, and API are all source-agnostic.
"""
from __future__ import annotations

from app.collectors.base import BaseCollector
from app.collectors.hc911 import HC911Collector
from app.config import Settings


def build_collectors(settings: Settings) -> list[BaseCollector]:
    collectors: list[BaseCollector] = []

    if settings.hc911_enabled:
        collectors.append(HC911Collector(settings))

    # Future sources, e.g.:
    #   collectors.append(AprsCollector(settings))
    #   collectors.append(WeatherCollector(settings))

    return collectors
