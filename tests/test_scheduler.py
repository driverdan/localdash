"""Pure tests for the scheduler's job specs, registration loop and wrapper (no DB)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import pytest

from app.collect import run_collector
from app.config import Settings
from app.events.refresh import refresh as events_refresh
from app.news.refresh import refresh as news_refresh
from app.scheduler import JobSpec, _run_job, build_scheduler, job_specs
from app.weather.refresh import refresh as weather_refresh


class FakeCollector:
    def __init__(self, source_key: str, poll_interval: int):
        self.source_key = source_key
        self.name = source_key
        self.poll_interval = poll_interval


def _settings(**overrides) -> Settings:
    values = {
        "news_enabled": True,
        "news_refresh_minutes": 15,
        "events_enabled": True,
        "events_refresh_minutes": 60,
        "weather_enabled": True,
        "weather_cache_minutes": 10,
    }
    return Settings(**(values | overrides))


def _collectors() -> dict[str, FakeCollector]:
    return {"hc911": FakeCollector("hc911", 60), "tnaw": FakeCollector("tnaw", 300)}


def test_job_specs_ids_intervals_and_funcs():
    collectors = _collectors()

    specs = {s.id: s for s in job_specs(_settings(), collectors)}

    assert list(specs) == ["hc911", "tnaw", "news_refresh", "events_refresh", "weather_refresh"]
    assert {k: s.interval_seconds for k, s in specs.items()} == {
        "hc911": 60,
        "tnaw": 300,
        "news_refresh": 15 * 60,
        "events_refresh": 60 * 60,
        "weather_refresh": 10 * 60,
    }
    assert all(s.enabled for s in specs.values())
    assert specs["hc911"].func is run_collector
    assert specs["hc911"].args == (collectors["hc911"],)
    assert specs["tnaw"].args == (collectors["tnaw"],)
    assert specs["news_refresh"].func is news_refresh
    assert specs["events_refresh"].func is events_refresh
    assert specs["weather_refresh"].func is weather_refresh
    assert specs["news_refresh"].args == ()


@pytest.mark.parametrize(
    ("flag", "job_id"),
    [
        ("news_enabled", "news_refresh"),
        ("events_enabled", "events_refresh"),
        ("weather_enabled", "weather_refresh"),
    ],
)
def test_job_specs_disabled_feature_is_marked_disabled(flag, job_id):
    specs = {s.id: s for s in job_specs(_settings(**{flag: False}), _collectors())}

    assert specs[job_id].enabled is False
    assert all(s.enabled for k, s in specs.items() if k != job_id)


async def _noop(*args) -> None:
    return None


def test_build_scheduler_registers_enabled_specs_with_shared_options():
    specs = [
        JobSpec(id="a", func=_noop, interval_seconds=30),
        JobSpec(id="b", func=_noop, interval_seconds=600, args=(1,)),
        JobSpec(id="off", func=_noop, interval_seconds=60, enabled=False),
    ]

    scheduler = build_scheduler(specs)
    jobs = {job.id: job for job in scheduler.get_jobs()}

    assert set(jobs) == {"a", "b"}
    now = datetime.now(timezone.utc)
    for spec in specs[:2]:
        job = jobs[spec.id]
        assert job.func is _run_job
        assert job.name == spec.id
        assert job.args == (spec,)
        assert job.max_instances == 1
        assert job.coalesce is True
        assert job.trigger.interval == timedelta(seconds=spec.interval_seconds)
        assert abs(job.next_run_time - now) < timedelta(seconds=5)


async def test_run_job_logs_failure_and_returns(caplog):
    async def boom():
        raise RuntimeError("upstream down")

    spec = JobSpec(id="news_refresh", func=boom, interval_seconds=60)

    with caplog.at_level(logging.ERROR, logger="app.scheduler"):
        await _run_job(spec)

    [record] = [r for r in caplog.records if r.name == "app.scheduler"]
    assert record.levelno == logging.ERROR
    assert record.getMessage() == "refresh job news_refresh failed"
    assert "upstream down" in caplog.text  # traceback is logged too


async def test_run_job_awaits_func_with_args():
    calls = []

    async def func(*args):
        calls.append(args)

    await _run_job(JobSpec(id="hc911", func=func, interval_seconds=60, args=("x", 2)))

    assert calls == [("x", 2)]
