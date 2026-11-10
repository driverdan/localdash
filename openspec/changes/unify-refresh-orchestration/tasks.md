## 0. Preconditions

- [x] 0.1 Check whether `extract-orm-base` has merged. If it has, import `Diff` from `app.diff`
  (not `app.schemas`) in the tests touched below. Nothing else in this change depends on it

## 1. Move the weather cycle beside the weather service

- [x] 1.1 Create `app/weather/refresh.py` with:
  - a `_last_payload: dict | None = None` module global;
  - an async `refresh()` that awaits `service.get_current(force=True)` and lets exceptions
    propagate;
  - when that payload differs from `_last_payload`, store it and await `manager.ping("weather")`;
  - logger `localdash.weather`;
  - a module docstring that explains why the comparison is against the last scheduled payload
    rather than the cache (design decision 6)
- [x] 1.2 Remove `_last_weather_payload`, `run_weather_refresh` and the `weather_service` import
  from `app/scheduler.py`

## 2. Move the timeseries cycle to `app/collect.py`

- [x] 2.1 Create `app/collect.py` and move these into it unchanged:
  - `_source_locks`, `_source_lock()` and `run_collector(collector)`, with the same return shape;
  - `_record_run()`, with the same upsert and still redacting the error text.

  Use logger `localdash.collect`. Write a module docstring saying it runs one collection cycle end
  to end (collector → `ingest` → diff broadcast → `sources` telemetry), and that it is shared by
  the scheduled tick and the manual refresh endpoint
- [x] 2.2 In `app/api/timeseries.py`, replace the in-handler `from app.scheduler import
  run_collector` with a top-level `from app.collect import run_collector`
- [x] 2.3 Remove `run_collector`, `_source_lock(s)`, `_record_run` and their now-unused imports
  from `app/scheduler.py`. The imports to drop are `ingest`, `Source`, `redact`, `pg_insert`,
  `SessionLocal`, `manager` and `asyncio`
- [x] 2.4 Update the docstrings in `app/collectors/__init__.py` and `app/collectors/base.py` that
  name "the scheduler" as the caller, so they point at `app/collect.py`

## 3. Scheduler as job specs plus one loop

- [x] 3.1 Add a frozen `JobSpec` dataclass (`id`, `func`, `interval_seconds`, `enabled`, `args`)
  to `app/scheduler.py`
- [x] 3.2 Add a pure `job_specs(settings, collectors) -> list[JobSpec]`. It returns one spec per
  collector, plus one each for `news_refresh`, `events_refresh` and `weather_refresh`:
  - **collector specs:** id = source key, `poll_interval` seconds, `args=(collector,)`,
    func = `run_collector`;
  - **feature specs:** minutes converted to seconds, and `enabled` taken from `news_enabled`,
    `events_enabled` and `weather_enabled`
- [x] 3.3 Add `_run_job(spec)`, the single try / `log.exception("refresh job %s failed", spec.id)`
  wrapper, and delete `run_news_refresh` and `run_events_refresh`
- [x] 3.4 Rewrite `build_scheduler(specs) -> AsyncIOScheduler` as one loop. It skips disabled
  specs and registers `_run_job` with:
  - `args=[spec]` and `id=spec.id`;
  - an `"interval"` trigger with `seconds=spec.interval_seconds`;
  - `next_run_time=now`, `max_instances=1` and `coalesce=True`
- [x] 3.5 Update the scheduler module docstring to say it composes jobs and contains no cycle logic

## 4. Lifespan wiring

- [x] 4.1 In `app/main.py`'s `lifespan`:
  - build `collectors = {c.source_key: c for c in build_collectors(settings)}`;
  - set `app.state.collectors`;
  - call `build_scheduler(job_specs(settings, collectors))`;
  - keep `app.state.scheduler`, `start()` and `shutdown(wait=False)` as they are
- [x] 4.2 Grep `app/` and `tests/` for `run_weather_refresh`, `run_news_refresh`,
  `run_events_refresh`, `_last_weather_payload`, `scheduler_mod` and `app.scheduler`, and fix any
  remaining references

## 5. Tests

- [x] 5.1 `tests/test_live_signals.py`: point the weather tests at `app.weather.refresh`:
  - patch `service`, `manager` and `_last_payload`;
  - `test_weather_job_failure_is_silent` now asserts that `refresh()` raises and that there was no
    ping and no `_last_payload` update;
  - update the module docstring
- [x] 5.2 `tests/test_live_signals.py`: point `_patch_collector_cycle` and the two concurrency
  tests at `app.collect` (`SessionLocal`, `ingest`, `_record_run`, `manager`, `_source_locks`)
- [x] 5.3 `tests/test_live_signals.py`: add a weather test for the scenario "Weather change made by
  a request-driven refresh is still signalled". Use a fake service whose payload changes with no
  job call in between, and assert that the next `refresh()` pings
- [x] 5.4 `tests/test_live_signals.py`: add timeseries tests:
  - a non-empty diff is broadcast once;
  - an empty diff broadcasts nothing;
  - a collector that raises still calls `_record_run` with status `error` and redacted error text,
    and returns `{source, status: "error", error, count: 0}`
- [x] 5.5 New `tests/test_scheduler.py` (pure, no DB): call `job_specs(...)` with a settings
  object and two fake collectors. Assert ids, intervals in seconds and `enabled` flags. Turning off
  `news_enabled`, `events_enabled` or `weather_enabled` marks that spec `enabled=False`
- [x] 5.6 `tests/test_scheduler.py`: build an unstarted scheduler from specs, one of them
  disabled, and assert that:
  - `get_jobs()` has exactly the enabled ids;
  - every job has `max_instances == 1`, `coalesce is True` and a `next_run_time` within a few
    seconds of now;
  - every job's func is `_run_job`
- [x] 5.7 `tests/test_scheduler.py`: when the spec's func raises, `_run_job` returns normally and
  logs `refresh job <id> failed` at ERROR (check with `caplog`). When the func succeeds, it is
  awaited with its args
- [x] 5.8 Confirm `tests/test_api_timeseries.py` (manual refresh endpoint, 404 for unknown key)
  passes unchanged. Adjust it only if it patched `app.scheduler`

## 6. Documentation

- [x] 6.1 `AGENTS.md`, "Scheduling — APScheduler" paragraph: the scheduler builds a list of job
  specs and registers them in one loop, with shared options and one error-logging wrapper. Each
  cycle lives beside the code it drives: `app/news/refresh.py`, `app/events/refresh.py`,
  `app/weather/refresh.py` and `app/collect.py`. Describe where things are, not a rule about
  feature ownership
- [x] 6.2 `AGENTS.md`, timeseries pipeline section:
  - add `app/collect.py` to the list of modules that make up the pipeline;
  - steps 1 and 4 name `app/collect.py` (the cycle, the per-source lock and the diff broadcast)
    instead of `scheduler.py`;
  - the `sources` table note says "written by `app/collect.py`'s `_record_run`";
  - the manual refresh route note still says it is serialized with the scheduled tick
- [x] 6.3 `AGENTS.md`, weather section: the `weather_refresh` job calls `app/weather/refresh.py`.
  That module forces the refresh and pings when the payload differs from the one the previous
  scheduled refresh produced
- [x] 6.4 `AGENTS.md`: add a short note on adding a scheduled job. Write the cycle (its lock,
  session and signal) somewhere cohesive with the code it runs, then add one `JobSpec` in
  `job_specs()`. Also check `README.md` and `CONTRIBUTING.md` for scheduler references and update
  any you find

## 7. Verification

- [x] 7.1 `pytest` passes with the compose DB up, including the new and moved tests
- [x] 7.2 `ruff` and the pre-commit hooks pass on the changed files
- [x] 7.3 Run `docker compose up --build` and check:
  - the logs show one immediate run of every enabled job at startup;
  - the logs show no `apscheduler` "raised an exception" lines;
  - `POST /api/v1/timeseries/sources/hc911/refresh` returns `{source, status, error, count}` and
    updates `GET /api/v1/timeseries/sources`
- [x] 7.4 `openspec validate unify-refresh-orchestration --strict` passes
