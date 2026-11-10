## Why

Every feature runs the same loop: serialize the scheduled and manual paths, run one cycle, tell
clients. That loop is written four different ways, and `app/scheduler.py` contains half of it:

- News and events each have a `refresh.py` next to the code they drive. Each holds a module-level
  `_refresh_lock`, its own `SessionLocal()` session and the `manager.ping(...)` call.
- The timeseries cycle lives in the scheduler module: `run_collector`, `_source_lock` /
  `_source_locks` and `_record_run` (`app/scheduler.py:70-127`). Because of that, the manual
  refresh endpoint imports it lazily inside the handler (`app/api/timeseries.py:260`). The
  collectors dict reaches the API through `app.state.collectors` only because `build_scheduler()`
  returns `(scheduler, collectors)` (`app/main.py:122-123`).
- Weather's change detection and ping also live in the scheduler (`_last_weather_payload` and
  `run_weather_refresh`, `app/scheduler.py:34,53-67`), while its cache is in
  `app/weather/service.py`.
- `app/scheduler.py:37-50` has two identical try/log wrappers, and `app/scheduler.py:135-174` has
  four near-identical `add_job` blocks.
- `tests/test_live_signals.py:141-196` has to monkeypatch scheduler module attributes one by one
  to test timeseries and weather behaviour that has nothing to do with scheduling.

This change is about cohesion: each cycle should live beside the code it runs, and the scheduler
should compose jobs without implementing any of them. With that done, adding a scheduled job
means writing its cycle where it fits and adding one job spec. It does not mean editing the
scheduler in three places.

## What Changes

- **Weather cycle → `app/weather/refresh.py`.** The new module sits next to the weather service
  it drives. It holds the forced cache refresh, the "payload changed since the last scheduled
  refresh" check and the `weather` ping. It raises on failure, as news and events already do, so
  the shared scheduler wrapper does the logging.
- **Timeseries cycle → `app/collect.py`.** This new top-level module sits next to `app/ingest.py`.
  It holds:
  - `run_collector(collector)`, which keeps its current name and return shape;
  - the per-source locks;
  - the diff broadcast;
  - the `sources` telemetry write (`_record_run`), including redaction of the stored error text.

  `POST /api/v1/timeseries/sources/{key}/refresh` imports it at module top level.
- **The scheduler shrinks to three pieces**, and imports the cycles rather than implementing them:
  - a pure `job_specs(settings, collectors)` that returns a list of `JobSpec` (id, coroutine
    function, args, interval in seconds, enabled);
  - one `add_job` loop that applies the shared options (immediate first run, `max_instances=1`,
    `coalesce=True`);
  - one error-logging wrapper around every job.
- **`build_scheduler()` returns only the scheduler.** The lifespan in `app/main.py` builds the
  collectors itself, stores them on `app.state.collectors` and passes them into the scheduler.
- **Tests** for the weather and timeseries cycles patch the modules that now hold those cycles. New
  pure tests cover the job spec list and the shared wrapper.
- **`AGENTS.md`** is updated to describe where each refresh cycle lives.

Observable changes, none of them in API responses, WebSocket messages, job ids, intervals or
database contents:

- Failed-job log lines change to one shared wording under `localdash.scheduler`. For example,
  `news refresh failed` becomes `refresh job news_refresh failed`.
- A failure in the timeseries telemetry write is now logged by the shared wrapper. Today it
  escapes to APScheduler's own `Job ... raised an exception` log.

## Capabilities

### New Capabilities
- `refresh-scheduling`: what every scheduled refresh job has in common, which until now lived only
  in code:
  - stable job ids;
  - feature gating;
  - an immediate first run at startup;
  - no overlapping or queued-up ticks (`max_instances=1`, `coalesce=True`);
  - failure isolation: a failed cycle is logged and never stops the scheduler or other jobs;
  - the scheduler only invokes refresh entry points and holds no cycle logic.

### Modified Capabilities
- `live-updates`: "Update signals are emitted at refresh choke points" now says the signal decision
  belongs to the refresh entry point that the scheduled and manual triggers share, not to the
  scheduler. It also describes the weather comparison exactly: against the payload the previous
  scheduled refresh produced. The ping rules themselves do not change.
- `timeseries`: "Manual source refresh" now says the manual endpoint and the scheduled tick run the
  same collection cycle, so a manual refresh records `sources` telemetry and broadcasts its diff
  exactly as a scheduled one does.
- `weather`: "Response caching and staleness" now says the ping fires when the shaped payload
  differs from the one the previous scheduled refresh produced. The current spec says "the
  previously cached one", but the code has always compared against the job's last-seen payload.
  The two differ when a request-driven refresh updated the cache in between.

## Impact

- **New modules:** `app/weather/refresh.py` and `app/collect.py`.
- **Rewritten:** `app/scheduler.py`, as a spec list plus one loop.
- **Updated:**
  - the lifespan in `app/main.py`;
  - `app/api/timeseries.py`, where the lazy import becomes a top-level import.
- **Unchanged:** `app/news/refresh.py`, `app/events/refresh.py`, `app/ingest.py` and
  `app/collectors/`.
- **Tests:** `tests/test_live_signals.py` is pointed at the new modules, and
  `tests/test_scheduler.py` is new.
- **Docs:** `AGENTS.md`: the scheduling paragraph, the timeseries pipeline steps, the `sources`
  table note and the weather pipeline paragraph.
- **Sibling changes:**
  - No package move is needed.
  - `relax-backend-feature-separation` lands first and records that backend modules may import
    freely. This change follows that stance.
  - If `extract-orm-base` has landed, `Diff` is imported from `app.diff`.
- No new dependencies, no migration and no frontend change.
