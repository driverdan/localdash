"""Offline tests for live-update signal emission (no DB, no network).

The refresh choke points own the pings, so these monkeypatch each module's
collaborators and assert on a fake manager — covering: news pings every
completed cycle, events pings only when data changed, weather pings only when
the shaped payload changed.
"""

from __future__ import annotations

import asyncio

import pytest

import app.events.refresh as events_refresh_mod
import app.news.refresh as news_refresh_mod
import app.scheduler as scheduler_mod
from app.schemas import Diff


class FakeManager:
    def __init__(self):
        self.pings: list[str] = []

    async def ping(self, topic: str):
        self.pings.append(topic)


class FakeSessionLocal:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, *args):
        return False


class FakeNominatimGeocoder:
    """Stands in for NominatimGeocoder, which refresh() opens with `async with`."""

    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


@pytest.fixture
def fake_manager():
    return FakeManager()


async def test_news_refresh_pings_every_completed_cycle(monkeypatch, fake_manager):
    async def fake_fetch_all(session):
        return {"feed": "ok"}

    async def fake_recluster(session):
        return 3

    monkeypatch.setattr(news_refresh_mod, "SessionLocal", FakeSessionLocal)
    monkeypatch.setattr(news_refresh_mod, "fetch_all", fake_fetch_all)
    monkeypatch.setattr(news_refresh_mod, "recluster", fake_recluster)
    monkeypatch.setattr(news_refresh_mod, "manager", fake_manager)

    await news_refresh_mod.refresh()

    assert fake_manager.pings == ["news"]


async def test_news_refresh_failure_does_not_ping(monkeypatch, fake_manager):
    async def failing_fetch_all(session):
        raise RuntimeError("upstream down")

    monkeypatch.setattr(news_refresh_mod, "SessionLocal", FakeSessionLocal)
    monkeypatch.setattr(news_refresh_mod, "fetch_all", failing_fetch_all)
    monkeypatch.setattr(news_refresh_mod, "manager", fake_manager)

    with pytest.raises(RuntimeError):
        await news_refresh_mod.refresh()

    assert fake_manager.pings == []


def _patch_events_cycle(monkeypatch, fake_manager, run_stats, retry_stats, reconciled):
    async def fake_run_sources(session, sources, geocoder, max_miles):
        return dict(run_stats)

    async def fake_retry(session, geocoder, retry_hours, batch):
        return dict(retry_stats)

    async def fake_reconcile(session):
        return reconciled

    monkeypatch.setattr(events_refresh_mod, "SessionLocal", FakeSessionLocal)
    monkeypatch.setattr(events_refresh_mod, "build_sources", lambda settings: [])
    monkeypatch.setattr(events_refresh_mod, "NominatimGeocoder", FakeNominatimGeocoder)
    monkeypatch.setattr(events_refresh_mod, "run_sources", fake_run_sources)
    monkeypatch.setattr(events_refresh_mod, "retry_failed_geocodes", fake_retry)
    monkeypatch.setattr(events_refresh_mod, "reconcile_events", fake_reconcile)
    monkeypatch.setattr(events_refresh_mod, "manager", fake_manager)


async def test_events_refresh_pings_when_data_changed(monkeypatch, fake_manager):
    _patch_events_cycle(
        monkeypatch,
        fake_manager,
        run_stats={"created": 1, "merged": 0, "skipped_far": 0},
        retry_stats={"retried": 0, "resolved": 0},
        reconciled=0,
    )

    await events_refresh_mod.refresh()

    assert fake_manager.pings == ["events"]


async def test_events_refresh_unchanged_cycle_is_silent(monkeypatch, fake_manager):
    _patch_events_cycle(
        monkeypatch,
        fake_manager,
        run_stats={"created": 0, "merged": 0, "skipped_far": 2},
        retry_stats={"retried": 3, "resolved": 0},
        reconciled=0,
    )

    await events_refresh_mod.refresh()

    assert fake_manager.pings == []


class FakeWeatherService:
    def __init__(self, payloads):
        self._payloads = list(payloads)
        self.forced: list[bool] = []

    async def get_current(self, *, force: bool = False):
        self.forced.append(force)
        result = self._payloads.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


async def test_weather_job_pings_only_on_payload_change(monkeypatch, fake_manager):
    svc = FakeWeatherService(
        [
            {"current": {"temp": 70}},
            {"current": {"temp": 70}},  # unchanged
            {"current": {"temp": 75}},  # changed
        ]
    )
    monkeypatch.setattr(scheduler_mod, "weather_service", svc)
    monkeypatch.setattr(scheduler_mod, "manager", fake_manager)
    monkeypatch.setattr(scheduler_mod, "_last_weather_payload", None)

    await scheduler_mod.run_weather_refresh()
    await scheduler_mod.run_weather_refresh()
    await scheduler_mod.run_weather_refresh()

    assert fake_manager.pings == ["weather", "weather"]
    assert svc.forced == [True, True, True]  # every tick bypasses the TTL


async def test_weather_job_failure_is_silent(monkeypatch, fake_manager):
    svc = FakeWeatherService([RuntimeError("NWS down")])
    monkeypatch.setattr(scheduler_mod, "weather_service", svc)
    monkeypatch.setattr(scheduler_mod, "manager", fake_manager)
    monkeypatch.setattr(scheduler_mod, "_last_weather_payload", None)

    await scheduler_mod.run_weather_refresh()

    assert fake_manager.pings == []


class _Recorder:
    """Records collector-cycle enter/exit events to detect overlap."""

    def __init__(self):
        self.events: list[str] = []


class FakeCollector:
    def __init__(self, source_key: str, rec: _Recorder):
        self.source_key = source_key
        self.name = source_key
        self.poll_interval = 60
        self._rec = rec

    async def collect(self):
        self._rec.events.append(f"start:{self.source_key}")
        await asyncio.sleep(0.01)
        self._rec.events.append(f"end:{self.source_key}")
        return []


def _patch_collector_cycle(monkeypatch, fake_manager):
    async def fake_ingest(session, source_key, observations):
        return Diff(source_key=source_key)

    async def fake_record(*args, **kwargs):
        return None

    monkeypatch.setattr(scheduler_mod, "SessionLocal", FakeSessionLocal)
    monkeypatch.setattr(scheduler_mod, "ingest", fake_ingest)
    monkeypatch.setattr(scheduler_mod, "_record_run", fake_record)
    monkeypatch.setattr(scheduler_mod, "manager", fake_manager)
    monkeypatch.setattr(scheduler_mod, "_source_locks", {})


async def test_same_source_collector_runs_are_serialized(monkeypatch, fake_manager):
    _patch_collector_cycle(monkeypatch, fake_manager)
    rec = _Recorder()
    scheduled, manual = FakeCollector("hc911", rec), FakeCollector("hc911", rec)

    results = await asyncio.gather(
        scheduler_mod.run_collector(scheduled), scheduler_mod.run_collector(manual)
    )

    assert [r["status"] for r in results] == ["ok", "ok"]
    assert rec.events == ["start:hc911", "end:hc911", "start:hc911", "end:hc911"]


async def test_different_sources_run_concurrently(monkeypatch, fake_manager):
    _patch_collector_cycle(monkeypatch, fake_manager)
    rec = _Recorder()

    await asyncio.gather(
        scheduler_mod.run_collector(FakeCollector("hc911", rec)),
        scheduler_mod.run_collector(FakeCollector("epb", rec)),
    )

    assert rec.events[:2] == ["start:hc911", "start:epb"]


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
