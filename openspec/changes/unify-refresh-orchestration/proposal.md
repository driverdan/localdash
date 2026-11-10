## Why

Every feature runs the same loop: serialize the scheduled and manual paths, run one cycle, tell
clients. That loop is written four different ways, and `app/scheduler.py` holds part of it for
every feature:

- News and events each own a `refresh.py` with a module-level `_refresh_lock`, their own
  `SessionLocal()` session and the `manager.ping(...)` call. This is the pattern the other two
  features should follow.
- The timeseries cycle lives in the scheduler module: `run_collector`, `_source_lock` /
  `_source_locks` and `_record_run` (`app/scheduler.py:70-127`). The manual refresh endpoint
  imports it lazily inside the handler (`app/api/timeseries.py:260`). The collectors dict reaches
  the API through `app.state.collectors` only because `build_scheduler()` returns
  `(scheduler, collectors)` (`app/main.py:122-123`).
- Weather's change detection and ping live in the scheduler too (`_last_weather_payload` and
  `run_weather_refresh`, `app/scheduler.py:34,53-67`), while its cache is in
  `app/weather/service.py`.
- `app/scheduler.py:37-50` has two identical try/log wrappers, and `app/scheduler.py:135-174` has
  four near-identical `add_job` blocks.
- `tests/test_live_signals.py:141-196` monkeypatches scheduler module attributes one at a time to
  test timeseries and weather behaviour that is not about scheduling.

Adding a fifth feature today means editing the scheduler in three places and copying one of two
patterns. After this change it means writing one `refresh.py` in the feature's package and adding
one job spec.

## What Changes

- **Weather** gets `app/weather/refresh.py`. It owns the forced cache refresh, the "payload changed
  since the last scheduled refresh" check and the `weather` ping. It raises on failure, like news
  and events, so the shared scheduler wrapper does the logging.
- **Timeseries** gets `app/timeseries/refresh.py`. It owns the collection cycle (today's
  `run_collector`, renamed `refresh(collector)`), the per-source locks, the diff broadcast and the
  `sources` telemetry write (`_record_run`, including redaction of the stored error text).
  `POST /api/v1/timeseries/sources/{key}/refresh` imports it at module top level, like the news and
  events routers import theirs.
- **The scheduler** reduces to:
  - a pure `job_specs(settings, collectors)` that returns a list of `JobSpec` (id, coroutine
    function, args, interval in seconds, enabled);
  - one `add_job` loop that applies the shared options (immediate first run, `max_instances=1`,
    `coalesce=True`);
  - one error-logging wrapper around every job.

  It imports each feature's refresh entry point but implements none of them.
- **`build_scheduler()`** returns only the scheduler. The lifespan in `app/main.py` builds the
  collectors itself, stores them on `app.state.collectors` and passes them into the scheduler.
- **Tests**: the weather and timeseries cycle tests move to the owning modules. New pure tests
  cover the job spec list and the shared wrapper.
- **`AGENTS.md`**: updated to describe where each feature's refresh cycle lives.

Observable changes, none of them to API responses, WebSocket messages, job ids, intervals or
database contents:

- Failed-job log lines change wording to one shared format under `localdash.scheduler`. For
  example, `news refresh failed` becomes `refresh job news_refresh failed`.
- A failure in the timeseries telemetry write, which today escapes to APScheduler's own
  `Job ... raised an exception` log, is now logged by the shared wrapper.

## Capabilities

### New Capabilities
- `refresh-scheduling`: the contract every scheduled refresh job shares. It covers stable job ids,
  feature gating, an immediate first run at startup, no overlapping or queued-up ticks
  (`max_instances=1`, `coalesce=True`), and failure isolation (a failed cycle is logged and never
  stops the scheduler or other jobs). Until now this lived only in code.

### Modified Capabilities
- `live-updates`: "Update signals are emitted at refresh choke points" now says that each
  feature's refresh entry point lives in that feature's package and decides its own signal, and
  that the scheduler only invokes it. It also states the weather comparison precisely: against
  the payload the previous scheduled refresh produced. The ping rules themselves are unchanged.
- `timeseries`: "Manual source refresh" now says that the manual endpoint and the scheduled tick
  run the same timeseries-owned cycle, so a manual refresh records `sources` telemetry and
  broadcasts its diff exactly as a scheduled one does.
- `weather`: "Response caching and staleness" corrects one phrase. The ping fires when the shaped
  payload differs from the one the previous scheduled refresh produced, not from "the previously
  cached one". The code has always compared against the job's last-seen payload, which matters
  when a request-driven refresh updated the cache in between.

## Impact

- Code:
  - New `app/weather/refresh.py` and `app/timeseries/refresh.py`.
  - `app/scheduler.py` rewritten to the spec list and loop.
  - `app/main.py` lifespan updated.
  - `app/api/timeseries.py`: the lazy import is replaced with a top-level one.
  - `app/news/refresh.py` and `app/events/refresh.py` are unchanged.
- Tests: `tests/test_live_signals.py` retargeted, plus a new `tests/test_scheduler.py`.
- Docs: `AGENTS.md` (scheduling paragraph, timeseries pipeline steps, the `sources` table note,
  the weather pipeline paragraph).
- Dependency: `app/timeseries/` is created by the sibling change `move-timeseries-into-package`.
  It should land first. design.md covers what to do if it has not.
- No new dependencies, no migration, no frontend change.
