"""Offline tests for live-update signal emission (no DB, no network).

The refresh choke points own the pings, so these monkeypatch each module's
collaborators and assert on a fake manager — covering: news pings every
completed cycle, events pings only when data changed, weather
(app/weather/refresh.py) pings only when the shaped payload differs from the one
the previous scheduled refresh produced, and the timeseries cycle
(app/collect.py) broadcasts only non-empty diffs, records telemetry and
serializes per source.
"""

from __future__ import annotations

import asyncio

import pytest

import app.collect as collect_mod
import app.events.refresh as events_refresh_mod
import app.news.refresh as news_refresh_mod
import app.weather.refresh as weather_refresh_mod
from app.diff import Diff
from app.redaction import REDACTED


class FakeManager:
    def __init__(self):
        self.pings: list[str] = []
        self.broadcasts: list[dict] = []

    async def ping(self, topic: str):
        self.pings.append(topic)

    async def broadcast(self, message: dict):
        self.broadcasts.append(message)


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


def _patch_weather_cycle(monkeypatch, fake_manager, svc):
    monkeypatch.setattr(weather_refresh_mod, "service", svc)
    monkeypatch.setattr(weather_refresh_mod, "manager", fake_manager)
    monkeypatch.setattr(weather_refresh_mod, "_last_payload", None)


async def test_weather_job_pings_only_on_payload_change(monkeypatch, fake_manager):
    svc = FakeWeatherService(
        [
            {"current": {"temp": 70}},
            {"current": {"temp": 70}},  # unchanged
            {"current": {"temp": 75}},  # changed
        ]
    )
    _patch_weather_cycle(monkeypatch, fake_manager, svc)

    await weather_refresh_mod.refresh()
    await weather_refresh_mod.refresh()
    await weather_refresh_mod.refresh()

    assert fake_manager.pings == ["weather", "weather"]
    assert svc.forced == [True, True, True]  # every tick bypasses the TTL


async def test_weather_job_failure_is_silent(monkeypatch, fake_manager):
    svc = FakeWeatherService([{"current": {"temp": 70}}, RuntimeError("NWS down")])
    _patch_weather_cycle(monkeypatch, fake_manager, svc)
    await weather_refresh_mod.refresh()
    fake_manager.pings.clear()

    # Failures propagate so the scheduler's shared wrapper logs them.
    with pytest.raises(RuntimeError):
        await weather_refresh_mod.refresh()

    assert fake_manager.pings == []
    assert weather_refresh_mod._last_payload == {"current": {"temp": 70}}


async def test_weather_change_from_request_refresh_still_pings(monkeypatch, fake_manager):
    svc = FakeWeatherService(
        [
            {"current": {"temp": 70}},  # scheduled refresh
            {"current": {"temp": 75}},  # request-driven lazy refresh (no ping)
            {"current": {"temp": 75}},  # next scheduled refresh: same as the cache
        ]
    )
    _patch_weather_cycle(monkeypatch, fake_manager, svc)

    await weather_refresh_mod.refresh()
    assert await svc.get_current() == {"current": {"temp": 75}}
    await weather_refresh_mod.refresh()

    # The comparison is against the previous scheduled payload, not the cache.
    assert fake_manager.pings == ["weather", "weather"]


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


def _patch_collector_cycle(monkeypatch, fake_manager, diff_for=None):
    """Patch app.collect's collaborators; returns the list of _record_run calls."""
    records: list[tuple] = []

    async def fake_ingest(session, source_key, observations):
        return diff_for(source_key) if diff_for else Diff(source_key=source_key)

    async def fake_record(collector, status, error, count):
        records.append((collector.source_key, status, error, count))

    monkeypatch.setattr(collect_mod, "SessionLocal", FakeSessionLocal)
    monkeypatch.setattr(collect_mod, "ingest", fake_ingest)
    monkeypatch.setattr(collect_mod, "_record_run", fake_record)
    monkeypatch.setattr(collect_mod, "manager", fake_manager)
    monkeypatch.setattr(collect_mod, "_source_locks", {})
    return records


async def test_collector_non_empty_diff_is_broadcast_once(monkeypatch, fake_manager):
    diff = Diff(source_key="hc911", closed=[7])
    records = _patch_collector_cycle(monkeypatch, fake_manager, diff_for=lambda key: diff)

    result = await collect_mod.run_collector(FakeCollector("hc911", _Recorder()))

    assert fake_manager.broadcasts == [diff.to_message()]
    assert result == {"source": "hc911", "status": "ok", "error": None, "count": 0}
    assert records == [("hc911", "ok", None, 0)]


async def test_collector_empty_diff_broadcasts_nothing(monkeypatch, fake_manager):
    records = _patch_collector_cycle(monkeypatch, fake_manager)

    await collect_mod.run_collector(FakeCollector("hc911", _Recorder()))

    assert fake_manager.broadcasts == []
    assert records == [("hc911", "ok", None, 0)]


class FailingCollector(FakeCollector):
    async def collect(self):
        raise RuntimeError("GET https://example.test/feed?api_key=hunter2 failed")


async def test_collector_failure_records_redacted_error(monkeypatch, fake_manager):
    records = _patch_collector_cycle(monkeypatch, fake_manager)

    result = await collect_mod.run_collector(FailingCollector("hc911", _Recorder()))

    error = result["error"]
    assert "hunter2" not in error
    assert REDACTED in error
    assert result == {"source": "hc911", "status": "error", "error": error, "count": 0}
    assert records == [("hc911", "error", error, 0)]
    assert fake_manager.broadcasts == []


async def test_same_source_collector_runs_are_serialized(monkeypatch, fake_manager):
    _patch_collector_cycle(monkeypatch, fake_manager)
    rec = _Recorder()
    scheduled, manual = FakeCollector("hc911", rec), FakeCollector("hc911", rec)

    results = await asyncio.gather(
        collect_mod.run_collector(scheduled), collect_mod.run_collector(manual)
    )

    assert [r["status"] for r in results] == ["ok", "ok"]
    assert rec.events == ["start:hc911", "end:hc911", "start:hc911", "end:hc911"]


async def test_different_sources_run_concurrently(monkeypatch, fake_manager):
    _patch_collector_cycle(monkeypatch, fake_manager)
    rec = _Recorder()

    await asyncio.gather(
        collect_mod.run_collector(FakeCollector("hc911", rec)),
        collect_mod.run_collector(FakeCollector("epb", rec)),
    )

    assert rec.events[:2] == ["start:hc911", "start:epb"]


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
