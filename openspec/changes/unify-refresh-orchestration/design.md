## Context

`app/scheduler.py` (176 lines) does two jobs at once. It wires up APScheduler, and it also
implements half of the refresh cycles. This is where each cycle lives today:

| Cycle | Lives in | Serialization | Session | Signal |
|---|---|---|---|---|
| news | `app/news/refresh.py` | module `_refresh_lock` | own `SessionLocal()` | ping after every completed cycle |
| events | `app/events/refresh.py` | module `_refresh_lock` | own `SessionLocal()` | ping only when created/merged/resolved/reconciled is nonzero |
| weather | `app/scheduler.py` (`run_weather_refresh`) | `WeatherService._lock` (in `service.py`) | none | ping only when the payload differs from `_last_weather_payload` |
| timeseries | `app/scheduler.py` (`run_collector`, `_source_lock`, `_record_run`) | per-source locks in `_source_locks` | two `SessionLocal()`s (ingest, telemetry) | broadcast the diff only when it is non-empty |

Every review finding checks out against `origin/main`, and the line numbers in the proposal are
current.

Two details shape the design:

- **APScheduler already survives a failing job.** APScheduler 3.11's `AsyncIOExecutor` catches
  exceptions from a job coroutine and logs `Job "..." raised an exception` through the
  `apscheduler` logger, so a failed job never kills the scheduler, wrapper or not. The two
  wrappers in `scheduler.py` exist so failures are logged under `localdash.scheduler` and stay out
  of APScheduler's error path.
- **`run_collector` handles its own errors, mostly.** It catches errors from collect and ingest,
  because it has to record them as telemetry. It does not catch a failure inside `_record_run`,
  which today reaches APScheduler's handler.
- **The manual endpoint borrows two things from the scheduler.** The manual timeseries endpoint
  needs the collectors dict and `run_collector`. Neither belongs to the scheduler.

This change follows the backend stance that sibling `relax-backend-feature-separation` writes
down. Backend packages are for organisation, not boundaries, and any module may import from any
other. So the motivation here is cohesion, not separation. A cycle should sit beside the code it
runs, and the scheduler should compose jobs without containing them. Nothing in this change asks
for a rule that each feature must own its cycle in its own package.

## Goals / Non-Goals

**Goals:**

- Each refresh cycle (its serialization, session and signal, plus the telemetry write for
  timeseries) lives beside the code it drives, and the scheduled and manual triggers both call it.
- `app/scheduler.py` contains no cycle logic. It builds a list of job specs, registers them in
  one loop, and wraps every job with one error logger.
- The collectors reach the API without passing through `build_scheduler()`'s return value.
- Tests of a cycle patch the module holding that cycle. Tests of scheduling test the job specs.
- Every runtime behaviour listed under "Preserved behaviour" stays the same.

**Non-Goals:**

- Adding a shared `RefreshCycle` base class, protocol or lock helper (see decision 5).
- Moving the timeseries pipeline into a package, or moving `app/ingest.py` or `app/collectors/`.
- Typing the dicts the refresh functions return. `add-typed-contracts` covers that.
- Removing per-attribute monkeypatching from the cycle tests. This change only moves the patch
  targets. It adds no injection seams; `inject-settings-and-clock` and `add-shared-http-client`
  cover that direction.
- Changing any interval, job id, ping rule or API response.
- Moving the lifespan or introducing an app factory. `extract-spa-serving` considers that.

## Preserved behaviour

The implementation must keep all of the following. tasks.md lists a test for each one.

1. **Job ids.** One job per collector, with id equal to `collector.source_key` (`hc911`, `tdot`,
   `epb`, `tnaw`). Also `news_refresh`, `events_refresh` and `weather_refresh`.
2. **Intervals and gating.**

   | Job | Interval | Gated by |
   |---|---|---|
   | each collector | `collector.poll_interval` seconds | always on |
   | news | `news_refresh_minutes` | `news_enabled` |
   | events | `events_refresh_minutes` | `events_enabled` |
   | weather | `weather_cache_minutes` | `weather_enabled` |

   The spec converts minutes to seconds. APScheduler's interval trigger treats `minutes=n` and
   `seconds=60*n` the same way.
3. **Immediate first run at startup** (`next_run_time=now`) for every job.
4. **`max_instances=1` and `coalesce=True`** for every job.
5. **Per-source serialization of timeseries cycles.** Manual and scheduled cycles for the same
   source are serialized, while different sources still run concurrently. News and events keep
   their single module lock, and weather keeps `WeatherService._lock`.
6. **Ping rules.**
   - News pings after every completed cycle and never after a failed one.
   - Events pings only when created, merged, resolved or reconciled is nonzero.
   - Weather pings only when the forced-refresh payload differs from the one the previous
     scheduled refresh produced, and a failed refresh never pings.
   - Timeseries broadcasts `diff.to_message()` only when the diff is non-empty.
7. **`sources` telemetry.** Every timeseries cycle, successful or not, upserts the `sources` row:
   name, poll interval, `last_run_at`, `last_status`, `last_error` and `last_count`. The stored
   error text passes through `app.redaction.redact` first. The manual endpoint's response stays
   `{source, status, error, count}`.
8. **Failure isolation.** A failed cycle never kills the scheduler or stops other jobs. It is
   logged, and the next tick retries.

## Decisions

### 1. Where each cycle lives

| Cycle | Module | Entry point | Holds |
|---|---|---|---|
| news | `app/news/refresh.py` | `refresh()` | unchanged |
| events | `app/events/refresh.py` | `refresh()` | unchanged |
| weather | `app/weather/refresh.py` (new) | `refresh()` | `_last_payload` module state, `service.get_current(force=True)`, the comparison and the `weather` ping |
| timeseries | `app/collect.py` (new) | `run_collector(collector)` | `_source_locks`, `_source_lock()`, the collect, ingest and broadcast cycle, `_record_run()` and redaction |

**Weather** goes next to the service it drives. Weather's `refresh()` now lets the service's
exception propagate instead of swallowing it. That matches news and events, and lets one scheduler
wrapper own failure logging. The comparison runs only after a successful fetch, so a failure
still pings nothing and leaves `_last_payload` untouched.

**Timeseries** goes to a new top-level `app/collect.py`. The timeseries pipeline is already a set
of top-level modules (`app/ingest.py`, `app/geojson.py`, `app/models.py`, plus the `app/collectors/`
package). `collect.py` names the pipeline step that drives the others: run a collector, hand the
batch to `ingest`, broadcast the diff and record the run. It is cohesive with what it calls and
reads naturally beside `ingest.py`. The function keeps its current name, `run_collector`, because
that name says what it does. Renaming it only to match `refresh()` elsewhere would be churn.

*Alternatives considered for the timeseries home:*

- **`app/collectors/refresh.py`.** Rejected. `app/collectors/` is the per-source plugin
  directory. Each module there imports only `base` and `config`, and its docstrings say collectors
  know nothing about ingest or storage. Adding a module that opens DB sessions, writes `sources`
  rows and broadcasts on the WebSocket bus would mix orchestration into the folder a contributor
  opens to add a source.
- **`app/ingest.py`.** Rejected. `ingest()` is a reconciliation function that takes a session.
  Its DB tests call it directly with a test session. Adding locks, its own `SessionLocal()`, the
  broadcast and the telemetry upsert would make it the largest module in the pipeline, with two
  unrelated reasons to change.
- **Keep it in `app/scheduler.py`.** Rejected, because that is the original problem. The manual
  API path would still import the scheduler, and cycle tests would still patch scheduler
  attributes.
- **An `app/timeseries/` package.** No longer planned (see Overlaps).

*Alternative considered for weather:* put change detection on `WeatherService`, for example as
`refresh_and_detect_change()`. Rejected. The cache serves both the request path and the job, but
only the job pings, so keeping the ping out of the service keeps the service about caching.

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
That way tests can check it without patching, and it fits `inject-settings-and-clock`. Disabled
features stay in the list with `enabled=False`. This keeps "disabled feature schedules nothing"
testable against the list, and the loop is the only place that filters.

The scheduler imports each cycle's entry point. It is where jobs are put together, just as
`main.py` is where routers are put together, and four imports cost less than a registration
mechanism.

*Alternative considered:* each feature exports its own `job_specs(settings)`, and the scheduler
concatenates them. Rejected. It spreads the job table over four files to save four imports, and
the timeseries specs would still need the collectors passed in.

### 3. One error-logging wrapper for every job

```python
async def _run_job(spec: JobSpec) -> None:
    try:
        await spec.func(*spec.args)
    except Exception:  # noqa: BLE001
        log.exception("refresh job %s failed", spec.id)
```

This replaces `run_news_refresh`, `run_events_refresh` and the try/except in
`run_weather_refresh`. It also wraps the timeseries jobs. Those still catch their own collect and
ingest errors, because those must become telemetry. So the wrapper only sees failures in the
telemetry write itself, which today go to APScheduler's logger.

*Alternative considered:* drop the wrappers and rely on APScheduler's own exception logging.
Rejected. Those lines go to the `apscheduler.executors` logger in APScheduler's format, which
would be a bigger observable change than one uniform message.

### 4. The lifespan builds the collectors, not the scheduler

`build_scheduler()` stops returning `(scheduler, collectors)`. The lifespan does:

```python
settings = get_settings()
collectors = {c.source_key: c for c in build_collectors(settings)}
app.state.collectors = collectors
scheduler = build_scheduler(job_specs(settings, collectors))
```

`app.state.collectors` stays how the manual endpoint finds a collector. It is FastAPI's
request-scoped way to reach objects built in the lifespan. `tests/test_api_routes.py` already
relies on the lifespan not running when the app is used outside a `with` block.

*Alternative considered:* a module-level `get_collectors()` cache in `app/collect.py`. Rejected,
because it adds a second global registry that tests would need to reset.

### 5. No shared helper for the lock, run, log and ping steps

The four cycles have the same overall shape but differ in the details:

- **Locks:** one module lock, per-source locks, or the service's own lock.
- **Sessions:** one, two or none.
- **Signals:** four different rules: always, on nonzero stats, on payload change, or on a
  non-empty diff carrying data.
- **Errors:** timeseries must turn its errors into telemetry rather than raise them.

A base class or a `serialized(lock_key)` / `run_cycle(lock, body, should_ping)` helper would need
a hook for each of these differences. The shared part left over, `async with lock:` and an `if`
around one `manager.ping`, is only a few lines per cycle.

*Re-checked under `relax-backend-feature-separation`:* the reasoning does not change. The
rejection was never about cross-package imports. A shared module such as `app/refresh.py` that
every cycle imports was allowed before (compare `app/redaction.py` and `app/ws.py`), and it is
explicitly allowed now. The helper is rejected on its merits, because it would cost more than it
saves. If `consolidate-shared-helpers` later finds a real duplicate, it can extract it. One
example is the lazy per-key lock idiom, if a second use appears.

### 6. Correct the weather spec wording, not the behaviour

The `weather` and `live-updates` specs say the ping fires when the payload differs from "the
previously cached one". The code compares against `_last_weather_payload`, the payload the
previous *job tick* produced. The two differ when a request-driven lazy refresh updated the cache
between ticks.

The code's choice is the right one. A lazy refresh does not ping, so comparing against the job's
last-seen payload means the next tick still tells clients about the change. The delta specs
reword the specs to match the code, and behaviour does not change.

## Overlaps with sibling changes

- **`relax-backend-feature-separation`** (lands first): records that backend packages are
  organisational and imports between them are free. This change relies on that stance. Under it,
  the scheduler importing every cycle, and `app/api/timeseries.py` importing `app/collect.py`, are
  ordinary imports. Nothing here adds a separation rule.
- **`ingest-owns-entity-status`** (1): changes what `ingest()` writes. `run_collector` calls
  `ingest()` unchanged, so there is no conflict.
- **`add-shared-http-client`** (2): touches `WeatherService._make_client`, not the refresh path. No
  conflict.
- **`extract-orm-base`** (3, formerly `move-timeseries-into-package`): no longer a dependency,
  because no package is created. Its overlap is import paths only:
  - `Diff` moves from `app.schemas` to `app.diff`, which affects `tests/test_live_signals.py`'s
    import;
  - `Source` keeps coming from `app.models`.

  Whichever change lands second adjusts those imports in `app/collect.py` and the tests.
- **`decompose-events-upsert`** (5): edits what `app/events/refresh.py` calls. This change does not
  touch that file, so there is no conflict.
- **`inject-settings-and-clock`** (6): `job_specs(settings, collectors)` already takes settings as
  an argument. The deeper `get_settings()` calls inside `app/events/refresh.py` and
  `WeatherService` belong to that change. If it wants a clock for `next_run_time` or for
  `_record_run`'s `last_run_at`, those now live in `app/scheduler.py` and `app/collect.py`.
- **`consolidate-shared-helpers`** (7): see decision 5.
- **`add-typed-contracts`** (8): types the dicts returned by news and events `refresh()` and by
  `run_collector`. This change keeps their shapes exactly. `JobSpec` is a plain dataclass and does
  not depend on it.
- **`extract-spa-serving`** (10): both edit the `lifespan` in `app/main.py`. If it introduces an
  app factory, the four lines from decision 4 move with the lifespan.
- **`tighten-python-tooling`** (11): the scheduler's three `# noqa: BLE001` comments become one (in
  `_run_job`), plus the existing one in `run_collector`. That change may still remove or keep them.
- **`remove-dead-schema`** (12): `_record_run` writes `Source.enabled=True`. Whichever change lands
  second drops or keeps that column in `_record_run` in `app/collect.py`.
- **`tidy-small-inconsistencies`** (13): concerns logger names. `app/weather/refresh.py` uses
  `localdash.weather`, `app/collect.py` uses `localdash.collect`, and the scheduler keeps
  `localdash.scheduler`.

## Risks / Trade-offs

- **[Log-line wording changes]** → Anyone grepping container logs for `news refresh failed` needs
  the new `refresh job <id> failed` form. The proposal calls this out, and no alerting in this
  repo depends on it.
- **[Module-level state in `app/weather/refresh.py`]** → This is today's global, just moved. Tests
  reset it with one `monkeypatch.setattr(weather_refresh, "_last_payload", None)`.
- **[`app/collect.py` versus `app/collectors/`, two similar names]** → The module docstring and the
  AGENTS.md pipeline steps say what each is for: `collectors/` holds the per-source fetch and
  normalize plugins, and `collect.py` runs one cycle of a collector end to end.
- **[Import cycles]** → `app/api/timeseries.py` will import `app.collect`, which imports `app.ws`,
  `app.db`, `app.ingest` and `app.models`. None of them imports `app.api`, so a top-level import is
  safe. The old lazy import kept the whole scheduler (APScheduler plus every cycle) out of the API
  module; it was not breaking a cycle.

## Migration Plan

This is a pure refactor with no data or config migration. To roll back, revert the
implementation PR.

## Open Questions

- Should `job_specs` live in `app/scheduler.py` (proposed) or next to the router wiring in
  `app/main.py`? The proposal keeps it in the scheduler so `main.py` stays a thin composition root
  and `extract-spa-serving` has less to move.
- Is `app/collect.py` the right name, or should it be something more explicit such as
  `app/collection_cycle.py`? The name is cheap to change before implementation.
