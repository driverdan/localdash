## Context

`app/scheduler.py` (176 lines) mixes two jobs: it wires APScheduler, and it implements half of
the features' refresh cycles. The current split:

| Feature | Cycle lives in | Serialization | Session | Signal |
|---|---|---|---|---|
| news | `app/news/refresh.py` | module `_refresh_lock` | own `SessionLocal()` | ping after every completed cycle |
| events | `app/events/refresh.py` | module `_refresh_lock` | own `SessionLocal()` | ping only when created/merged/resolved/reconciled is nonzero |
| weather | `app/scheduler.py` (`run_weather_refresh`) | `WeatherService._lock` (in `service.py`) | none | ping only when the payload differs from `_last_weather_payload` |
| timeseries | `app/scheduler.py` (`run_collector`, `_source_lock`, `_record_run`) | per-source locks in `_source_locks` | two `SessionLocal()`s (ingest, telemetry) | broadcast the diff only when it is non-empty |

Every review finding checks out against `origin/main`. The line numbers in the proposal are
current.

Two details matter for the design:

- APScheduler 3.11's `AsyncIOExecutor` already catches exceptions from a job coroutine and logs
  `Job "..." raised an exception` through the `apscheduler` logger. So the scheduler never dies on
  a failed job, wrapper or not. The two wrappers in `scheduler.py` exist to log under
  `localdash.scheduler` and to keep exceptions out of APScheduler's error path. `run_collector`
  catches its own collect/ingest errors because it must record them as telemetry. It does not
  catch a failure inside `_record_run`, which today reaches APScheduler's handler.
- The manual timeseries endpoint needs two things the scheduler happens to own: the collectors
  dict and `run_collector`. Neither belongs to the scheduler.

## Goals / Non-Goals

**Goals:**

- Each feature's refresh cycle (serialization, session, signal, and for timeseries the telemetry
  write) lives in that feature's package as `refresh.py`. Scheduled and manual triggers both call
  that module.
- `app/scheduler.py` holds no feature logic. It builds a list of job specs, registers them in one
  loop, and wraps every job with one error logger.
- The collectors reach the API without going through `build_scheduler()`'s return value.
- Tests of a feature's cycle patch that feature's module. Tests of scheduling test the job specs.
- All runtime behaviour listed under "Preserved behaviour" is unchanged.

**Non-Goals:**

- A shared `RefreshCycle` base class, protocol or lock helper (see decision 5).
- Typing the dicts the refresh functions return. `add-typed-contracts` owns that.
- Removing per-attribute monkeypatching from the cycle tests. This change moves the patch targets
  to the owning module. It does not add injection seams; `inject-settings-and-clock` and
  `add-shared-http-client` cover that direction.
- Changing any interval, job id, ping rule or API response.
- Moving the lifespan or introducing an app factory. `extract-spa-serving` weighs that.

## Preserved behaviour

The implementation must keep each of these. Each one has a test listed in tasks.md:

1. **Job ids**:
   - one job per collector with id equal to `collector.source_key` (`hc911`, `tdot`, `epb`,
     `tnaw`);
   - `news_refresh`, `events_refresh` and `weather_refresh`.
2. **Intervals and gating**:
   - collectors use `collector.poll_interval` seconds;
   - news uses `news_refresh_minutes`, gated by `news_enabled`;
   - events uses `events_refresh_minutes`, gated by `events_enabled`;
   - weather uses `weather_cache_minutes`, gated by `weather_enabled`.

   Minutes are converted to seconds in the spec. APScheduler's interval trigger treats
   `minutes=n` and `seconds=60*n` identically.
3. **Immediate first run at startup** (`next_run_time=now`) for every job.
4. **`max_instances=1` and `coalesce=True`** for every job.
5. **Per-source serialization** of manual and scheduled timeseries cycles. Different sources still
   run concurrently. News and events keep their single module lock, and weather keeps
   `WeatherService._lock`.
6. **Ping rules**:
   - news pings after every completed cycle and never after a failed one;
   - events pings only when created, merged, resolved or reconciled is nonzero;
   - weather pings only when the forced-refresh payload differs from the one the previous
     scheduled refresh produced, and a failed refresh never pings;
   - timeseries broadcasts `diff.to_message()` only when the diff is non-empty.
7. **`sources` telemetry**: every timeseries cycle, successful or not, upserts the `sources` row
   (name, poll interval, `last_run_at`, `last_status`, `last_error`, `last_count`). The stored
   error text passes through `app.redaction.redact` first. The manual endpoint's response stays
   `{source, status, error, count}`.
8. **A failed cycle never kills the scheduler** or stops other jobs. It is logged and the next
   tick retries.

## Decisions

### 1. Each feature exposes `refresh` from its own `refresh.py`

| Module | Entry point | Owns |
|---|---|---|
| `app/news/refresh.py` | `refresh()` | unchanged |
| `app/events/refresh.py` | `refresh()` | unchanged |
| `app/weather/refresh.py` (new) | `refresh()` | `_last_payload` module state, `service.get_current(force=True)`, the comparison and the `weather` ping |
| `app/timeseries/refresh.py` (new) | `refresh(collector)` | `_source_locks`, `_source_lock()`, the collect, ingest and broadcast cycle, `_record_run()` and redaction |

The timeseries function is renamed from `run_collector` to `refresh`. Every feature then exposes
the same name, and callers import the module (`from app.timeseries import refresh as
timeseries_refresh`), as `app/api/news.py` and `app/api/events.py` already do. This also avoids a
clash with the route handler, which is itself named `refresh`.

Weather's `refresh()` lets the service's exception propagate instead of swallowing it. That
matches news and events, and lets one scheduler wrapper own failure logging. Because the
comparison runs only after a successful fetch, a failure still pings nothing and leaves
`_last_payload` alone.

*Alternative considered:* put weather change detection on `WeatherService` (for example
`refresh_and_detect_change()`). Rejected because it would mix two concerns in one class: the cache
serves both the request path and the job, but only the job pings. A separate `refresh.py` matches
the other three features.

### 2. The scheduler is a list of job specs plus one loop

```python
@dataclass(frozen=True)
class JobSpec:
    id: str
    func: Callable[..., Awaitable[object]]
    interval_seconds: int
    enabled: bool = True
    args: tuple = ()

def job_specs(settings, collectors) -> list[JobSpec]: ...   # pure, no side effects

def build_scheduler(specs) -> AsyncIOScheduler:
    for spec in specs:
        if spec.enabled:
            scheduler.add_job(_run_job, "interval", seconds=spec.interval_seconds,
                              args=[spec], id=spec.id, next_run_time=now,
                              max_instances=1, coalesce=True)
```

`job_specs` takes `settings` and `collectors` as arguments instead of calling `get_settings()`.
Tests can then assert on it without patching, and that fits `inject-settings-and-clock`. Disabled
features stay in the list with `enabled=False`. This keeps "disabled feature schedules nothing"
testable against the list, and leaves the loop as the one place that filters.

The scheduler module still imports each feature's `refresh` module. It is the composition point
for jobs, just as `main.py` is for routers, and four imports are cheaper than a registration
mechanism.

*Alternative considered:* each feature exports its own `job_specs(settings)` and the scheduler
concatenates them. Rejected for now. It spreads the job table over four files to save four
imports, and timeseries would still need the collectors passed in.

### 3. One error-logging wrapper for every job

```python
async def _run_job(spec: JobSpec) -> None:
    try:
        await spec.func(*spec.args)
    except Exception:  # noqa: BLE001
        log.exception("refresh job %s failed", spec.id)
```

This replaces `run_news_refresh`, `run_events_refresh` and the try/except in
`run_weather_refresh`. It also wraps the timeseries jobs. The timeseries cycle still catches its
own collect/ingest errors, because those must become telemetry, so the wrapper only sees failures
in the telemetry write itself. Today those go to APScheduler's logger.

*Alternative considered:* drop the wrappers and rely on APScheduler's own exception logging.
Rejected because those lines go to the `apscheduler.executors` logger with APScheduler's format,
not ours. That would be a larger observable change than one uniform message.

### 4. Collectors are built in the lifespan, not by the scheduler

`build_scheduler()` stops returning `(scheduler, collectors)`. The lifespan does:

```python
settings = get_settings()
collectors = {c.source_key: c for c in build_collectors(settings)}
app.state.collectors = collectors
scheduler = build_scheduler(job_specs(settings, collectors))
```

`app.state.collectors` stays the way the manual endpoint finds a collector. It is the
request-scoped way to reach lifespan-built objects in FastAPI, and `tests/test_api_routes.py`
already relies on the app not running the lifespan when used outside `with`.

*Alternative considered:* a module-level `get_collectors()` cache in `app/timeseries/refresh.py`.
Rejected because it adds a second global registry, and tests would need to reset it.

### 5. No shared refresh abstraction

The four cycles share a shape but not their details:

- one lock versus per-source locks versus the service's lock;
- one session versus two versus none;
- four different signal rules.

A base class or `serialized(lock_key)` helper would have to grow a hook for each difference. The
unification here is about location and naming. Every feature has a `refresh.py` with a `refresh`
function that owns its lock, session and signal, and the scheduler treats them all the same way.
If `consolidate-shared-helpers` later finds a real duplicate (for example the
`lock = d.get(k) or d.setdefault(...)` idiom), it can extract it.

### 6. Where `app/timeseries/refresh.py` comes from if `move-timeseries-into-package` has not landed

The suggested landing order puts `move-timeseries-into-package` (3) before this change (4). The
move creates `app/timeseries/` and moves `ingest.py`, `models.py`, `schemas.py` and `collectors/`
into it. This change then adds `app/timeseries/refresh.py` next to them and imports
`app.timeseries.ingest`, `app.timeseries.models` and so on.

If this change is implemented first:

- Create `app/timeseries/__init__.py` (docstring only) and `app/timeseries/refresh.py` anyway,
  importing from the current top-level `app.ingest`, `app.models` and `app.collectors.base`.
- The move change then only rewrites those imports and must not overwrite the package's
  `__init__.py`. Note this in the move change's PR when it is implemented.
- Do **not** park the cycle in `app/collectors/refresh.py` or keep it in the scheduler as a stop-gap.
  Either option means a second move later and a second round of test retargeting.

### 7. Weather spec wording is corrected, not the behaviour

The `weather` and `live-updates` specs say the ping fires when the payload differs from "the
previously cached one". The code compares against `_last_weather_payload`, the payload the
previous *job tick* produced. These differ when a request-driven lazy refresh updated the cache
between ticks. The code's choice is the right one: a lazy refresh does not ping, so comparing
against the job's last-seen payload makes sure the next tick tells clients about that change. The
delta specs change the wording to match the code. Behaviour is unchanged.

## Overlaps with sibling changes

- `ingest-owns-entity-status` (1): changes what `ingest()` writes. The timeseries cycle calls
  `ingest()` unchanged, so there is no conflict.
- `add-shared-http-client` (2): touches `WeatherService._make_client`, not the refresh path. No
  conflict.
- `move-timeseries-into-package` (3): hard dependency for the module location. See decision 6.
- `decompose-events-upsert` (5): edits what `app/events/refresh.py` calls. This change does not
  touch that file, so there is no conflict.
- `inject-settings-and-clock` (6): `job_specs(settings, collectors)` already takes settings as an
  argument. The deeper `get_settings()` calls inside `app/events/refresh.py` and `WeatherService`
  belong to that change. If it wants a clock for `next_run_time` or `_record_run`'s
  `last_run_at`, those calls now live in `app/scheduler.py` and `app/timeseries/refresh.py`.
- `consolidate-shared-helpers` (7): see decision 5.
- `add-typed-contracts` (8): owns typing the dicts returned by `news`, `events` and timeseries
  `refresh()`. This change keeps their shapes exactly. `JobSpec` is a plain dataclass and does not
  depend on that change.
- `extract-spa-serving` (10): both edit `app/main.py`'s `lifespan`. If it introduces an app
  factory, decision 4's four lines move with the lifespan.
- `tighten-python-tooling` (11): the `# noqa: BLE001` comments shrink from three to one (in
  `_run_job`), plus the one in the timeseries cycle. It may still remove or keep them.
- `remove-dead-schema` (12): `_record_run` writes `Source.enabled=True`. Whichever change lands
  second drops or keeps that column in the moved `_record_run` in `app/timeseries/refresh.py`.
- `tidy-small-inconsistencies` (13): logger names. The new modules use `localdash.weather` and
  `localdash.timeseries`. The scheduler keeps `localdash.scheduler`.

## Risks / Trade-offs

- **[Log-line wording changes]** → Anyone grepping container logs for `news refresh failed` needs
  the new `refresh job <id> failed` form. This is called out in the proposal. No alerting depends
  on it in this repo.
- **[Module-level state in `app/weather/refresh.py`]** → It is the same pattern as today's global,
  just moved. Tests reset it with one `monkeypatch.setattr(weather_refresh, "_last_payload", None)`.
- **[Renaming `run_collector`]** → Only one production caller (the API) and the tests reference
  it. Grep for `run_collector` and `app.scheduler` in the verification task.
- **[Import cycles]** → `app/api/timeseries.py` will import `app.timeseries.refresh`, which
  imports `app.ws` and `app.db`. Neither imports `app.api`, so a top-level import is safe. The old
  lazy import was there to avoid pulling in the whole scheduler (APScheduler plus every feature),
  not to break a cycle.

## Migration Plan

This is a pure refactor with no data or config migration. To roll back, revert the
implementation PR.

## Open Questions

- Should `job_specs` live in `app/scheduler.py` (proposed) or in `app/main.py` next to the router
  wiring? Proposed: the scheduler, so `main.py` stays a thin composition root and
  `extract-spa-serving` has less to move.
