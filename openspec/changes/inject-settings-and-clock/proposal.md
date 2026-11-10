## Why

Pipeline code mixes two ways of getting configuration and the time. Some functions receive what
they need (`build_sources(settings)`, `run_sources(..., max_miles=...)`,
`retry_failed_geocodes(retry_hours=..., batch=...)`), while others reach for `get_settings()` deep
inside: `purge_blocked_tags` and `upsert_raw_events` read the tag blocklist, `upsert_raw_events`
reads `get_settings().center` inside its per-event loop even though it already takes `max_miles` as
a parameter, `recluster` reads the story window, and `WeatherService.get_current` reads the whole
settings object on every call. Tests for that code have to change process-global state to vary a
setting: `tests/test_events_ingest.py` monkeypatches attributes on the cached `Settings` object, and
`tests/test_weather.py` sets environment variables and calls `get_settings.cache_clear()` around
every test.

The clock has the same problem. `app/` calls `datetime.now(timezone.utc)` at 23 sites, and only the
zoo source (`_now()`, `parse_occurrence(text, now)`) lets a caller pin it. `AGENTS.md` and the
`test-isolation` spec tell test authors to "compute test dates relative to now or inject a fixed
now", but `reconcile_events(session)`, `retry_failed_geocodes`, `recluster` and `get_stories` give no
way to inject one. The last two date bugs (`fix-reconcile-test-dates`, `clamp-future-article-dates`)
were both worked around in tests because the code under test could not be given a time.
`fix-reconcile-test-dates` explicitly deferred an injectable `now` for `reconcile_events()`; this
change picks that up.

## What Changes

- Time-dependent pipeline functions take an optional keyword-only `now: datetime | None = None`,
  resolved once at the top to the current UTC time when omitted: `upsert_raw_events`,
  `run_sources`, `reconcile_events` and `retry_failed_geocodes` (`app/events/ingest.py`),
  `recluster` (`app/news/clustering.py`), `get_stories` (`app/news/stories.py`), and timeseries
  `ingest` (`app/ingest.py`). Callers that omit it behave as today.
- Pipeline functions stop calling `get_settings()`. The values they used are passed in by the
  layer that already owns the settings:
  - `purge_blocked_tags(session, blocked)` takes the blocklist; the app lifespan passes
    `settings.blocked_tags`.
  - `upsert_raw_events` and `run_sources` take `blocked_tags` and `center` alongside the existing
    `max_miles`; `app/events/refresh.py` passes them from the settings it already reads.
  - `recluster(session, *, window_days, now=None)` takes the story window; `app/news/refresh.py`
    passes `settings.news_story_window_days`.
  - `WeatherService` accepts an optional `Settings` at construction and uses it instead of calling
    `get_settings()` on every `get_current()`; the module singleton keeps resolving the process
    settings lazily.
- The three routers that read settings (`app/api/news.py`, `app/api/events.py`, `app/api/root.py`)
  receive them through FastAPI `Depends(get_settings)` instead of calling the global inside the
  handler, so tests can pass a `Settings` or use `app.dependency_overrides`.
- `get_settings()` is called only at composition roots: the refresh cycles, the scheduler, the app
  lifespan and `main.py`, `app/db.py`, `app/redaction.py`, and router dependencies.
- Tests stop mutating the cached `Settings` or the environment to vary a setting the code under
  test receives: they pass values or a locally built `Settings(_env_file=None, ...)` instead. New
  tests use a fixed `now` for `reconcile_events` and `retry_failed_geocodes`.
- `AGENTS.md` documents the rule (where `get_settings()` may be called; time-dependent pipeline
  functions take `now`).

**Observable changes (small, stated on purpose):**

- `retry_failed_geocodes` stamps every row it retries in one pass with the pass's resolved `now`
  instead of a fresh wall-clock reading per row, and `upsert_raw_events` stamps new geocode-cache
  rows with its batch `now`. Stamps in one pass were already within seconds of each other (the
  geocoder is throttled to about one request per second); retry eligibility is measured in hours.
- `upsert_raw_events` and `run_sources` called without `blocked_tags` apply no blocklist (today
  they silently read the configured one). Production goes through `refresh()`, which passes the
  configured blocklist, so the running app is unchanged.

Out of scope: event-source `fetch()` windows (CitySpark, tribe), the news fetcher's `fetched_at`
and `last_fetch` stamps, scheduler start times and run records, and the routers' "upcoming" and
`closed_within` cutoffs. These record or bound real I/O against the wall clock and nothing needs to
pin them today (see design.md). `app/redaction.py` keeps calling `get_settings()`: a process-wide
log filter has to read the live process settings, so its tests legitimately set the environment.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `test-isolation`: "Tests do not depend on the date they run" now states that time-dependent
  pipeline functions accept an injected `now`, so tests can use the "inject a fixed now" route it
  already names; a new requirement says tests vary configuration by passing values into the code
  under test, not by mutating the cached settings or the environment.

The `events`, `news`, `weather` and `timeseries` specs do not change: no endpoint, setting or
stored value behaves differently apart from the timestamp detail noted above.

## Impact

- `app/events/ingest.py`, `app/events/refresh.py`, `app/main.py` (lifespan purge call),
  `app/news/clustering.py`, `app/news/stories.py`, `app/news/refresh.py`, `app/ingest.py`,
  `app/weather/service.py`, `app/api/news.py`, `app/api/events.py`, `app/api/root.py`.
- Tests: `tests/test_events_ingest.py`, `tests/test_weather.py`, `tests/test_news_db.py`,
  `tests/test_api_events.py`, `tests/test_live_signals.py`, plus new fixed-`now` tests.
- `AGENTS.md` (Tests section and Config section).
- No dependency, schema, API-shape or configuration changes.
