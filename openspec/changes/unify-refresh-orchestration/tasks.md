## 0. Preconditions

- [ ] 0.1 Check whether `move-timeseries-into-package` has merged (`app/timeseries/` exists with
  `ingest.py`, `models.py`, `collectors/`). If it has not, follow design decision 6: create
  `app/timeseries/__init__.py` (docstring only) and import from the current top-level modules, and
  note in the implementation PR that the move must keep `refresh.py` and the package `__init__.py`

## 1. Weather owns its refresh

- [ ] 1.1 Create `app/weather/refresh.py`. It holds a `_last_payload: dict | None = None` module
  global and an async `refresh()` that:
  - awaits `service.get_current(force=True)`, letting exceptions propagate;
  - when the payload differs from `_last_payload`, stores it and awaits `manager.ping("weather")`;
  - uses logger `localdash.weather`;
  - has a module docstring explaining why the comparison is against the last scheduled payload
    rather than the cache (design decision 7)
- [ ] 1.2 Remove `_last_weather_payload`, `run_weather_refresh` and the `weather_service` import
  from `app/scheduler.py`

## 2. Timeseries owns its refresh

- [ ] 2.1 Create `app/timeseries/refresh.py` with `_source_locks`, `_source_lock()`,
  `refresh(collector)` (today's `run_collector` body, same return shape) and `_record_run()`
  (same upsert, still redacting the error text). Use logger `localdash.timeseries` and a module
  docstring matching the news and events `refresh.py` style
- [ ] 2.2 In `app/api/timeseries.py`, replace the in-handler `from app.scheduler import
  run_collector` with a top-level `from app.timeseries import refresh as timeseries_refresh`, and
  call `timeseries_refresh.refresh(collector)`
- [ ] 2.3 Remove `run_collector`, `_source_lock(s)`, `_record_run` and their now-unused imports
  (`ingest`, `Source`, `redact`, `pg_insert`, `SessionLocal`, `manager`, `asyncio`) from
  `app/scheduler.py`

## 3. Scheduler as job specs plus one loop

- [ ] 3.1 Add the frozen `JobSpec` dataclass (`id`, `func`, `interval_seconds`, `enabled`, `args`)
  to `app/scheduler.py`
- [ ] 3.2 Add the pure `job_specs(settings, collectors) -> list[JobSpec]`. It returns:
  - one spec per collector (id = source key, `poll_interval` seconds, `args=(collector,)`,
    func = `timeseries_refresh.refresh`);
  - `news_refresh`, `events_refresh` and `weather_refresh`, with minutes converted to seconds and
    `enabled` set from `news_enabled`, `events_enabled` and `weather_enabled`
- [ ] 3.3 Add `_run_job(spec)`, the single try/`log.exception("refresh job %s failed", spec.id)`
  wrapper, and delete `run_news_refresh` and `run_events_refresh`
- [ ] 3.4 Rewrite `build_scheduler(specs) -> AsyncIOScheduler` as one loop. It skips disabled
  specs and registers `_run_job` with `args=[spec]`, `id=spec.id`, the `"interval"` trigger with
  `seconds=spec.interval_seconds`, `next_run_time=now`, `max_instances=1` and `coalesce=True`
- [ ] 3.5 Update the scheduler module docstring. It wires jobs and holds no feature logic

## 4. Lifespan wiring

- [ ] 4.1 In `app/main.py`'s `lifespan`:
  - build `collectors = {c.source_key: c for c in build_collectors(settings)}`;
  - set `app.state.collectors`;
  - call `build_scheduler(job_specs(settings, collectors))`;
  - keep `app.state.scheduler`, `start()` and `shutdown(wait=False)` as they are
- [ ] 4.2 Grep `app/` and `tests/` for `run_collector`, `run_weather_refresh`,
  `run_news_refresh`, `run_events_refresh`, `_last_weather_payload` and `app.scheduler` and fix
  any remaining references

## 5. Tests

- [ ] 5.1 `tests/test_live_signals.py`:
  - retarget the weather tests to `app.weather.refresh`: patch `service`, `manager` and
    `_last_payload`;
  - `test_weather_job_failure_is_silent` now asserts that `refresh()` raises and that no ping or
    `_last_payload` update happened;
  - update the module docstring
- [ ] 5.2 `tests/test_live_signals.py`: retarget `_patch_collector_cycle` and the two concurrency
  tests to `app.timeseries.refresh` (`SessionLocal`, `ingest`, `_record_run`, `manager`,
  `_source_locks`), and call `refresh(collector)`
- [ ] 5.3 Add to `tests/test_live_signals.py` a weather test for the scenario "Weather change made
  by a request-driven refresh is still signalled". Use a fake service whose payload changes, with
  no job call in between, and assert that the next `refresh()` pings
- [ ] 5.4 Add to `tests/test_live_signals.py` timeseries tests:
  - a non-empty diff is broadcast once, and an empty diff broadcasts nothing;
  - a collector that raises still calls `_record_run` with status `error` and redacted error
    text, and returns `{source, status: "error", error, count: 0}`
- [ ] 5.5 New `tests/test_scheduler.py` (pure, no DB) testing `job_specs(...)` with a settings
  object and two fake collectors. Assert:
  - ids, intervals in seconds and `enabled` flags;
  - with `news_enabled`, `events_enabled` or `weather_enabled` false, that spec is
    `enabled=False`
- [ ] 5.6 `tests/test_scheduler.py`: build an unstarted scheduler from specs (one disabled) and
  assert:
  - `get_jobs()` has exactly the enabled ids;
  - every job has `max_instances == 1`, `coalesce is True` and a `next_run_time` within a few
    seconds of now;
  - every job's func is `_run_job`
- [ ] 5.7 `tests/test_scheduler.py`: `_run_job` with a spec whose func raises returns normally and
  logs `refresh job <id> failed` at ERROR (via `caplog`). A spec whose func succeeds is awaited
  with its args
- [ ] 5.8 Check that `tests/test_api_timeseries.py` (manual refresh endpoint, 404 for unknown key)
  still passes unchanged, and adjust it only if it patched `app.scheduler`

## 6. Documentation

- [ ] 6.1 `AGENTS.md` "Scheduling — APScheduler" paragraph: the scheduler is a list of job specs
  registered in one loop with shared options and one error-logging wrapper. Each feature's cycle
  lives in its own `refresh.py`
- [ ] 6.2 `AGENTS.md` timeseries pipeline section:
  - step 1 and step 4 name `app/timeseries/refresh.py` (the cycle, per-source lock and diff
    broadcast) instead of `scheduler.py`;
  - the `sources` table note says "written by `app/timeseries/refresh.py`'s `_record_run`";
  - the manual refresh route note still says it is serialized with the scheduled tick
- [ ] 6.3 `AGENTS.md` weather section: the `weather_refresh` job calls `app/weather/refresh.py`,
  which forces the refresh and pings when the payload differs from the previous scheduled
  refresh's
- [ ] 6.4 `AGENTS.md`: add a short "adding a refresh job" note. Write a `refresh.py` in the
  feature package that owns its lock, session and signal, then add one `JobSpec` in
  `job_specs()`. Check `README.md` and `CONTRIBUTING.md` for scheduler references and update any
  found

## 7. Verification

- [ ] 7.1 `pytest` passes (with the compose DB up), including the new and retargeted tests
- [ ] 7.2 `ruff` and the pre-commit hooks pass on the changed files
- [ ] 7.3 Run `docker compose up --build`. The logs show one immediate run of every enabled job at
  startup and no `apscheduler` "raised an exception" lines.
  `POST /api/v1/timeseries/sources/hc911/refresh` returns `{source, status, error, count}` and
  updates `GET /api/v1/timeseries/sources`
- [ ] 7.4 `openspec validate unify-refresh-orchestration --strict` passes
