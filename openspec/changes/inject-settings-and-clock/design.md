## Context

`get_settings()` (`app/config.py`) is an `lru_cache`d factory for the process `Settings`. Today it
is called from two kinds of places:

- **Composition roots**, which build the running app and its jobs: `app/db.py` (engine),
  `app/main.py` (title, weather router mount, lifespan), `app/scheduler.py`
  (`build_scheduler`), `app/events/refresh.py` (one refresh cycle), and `app/redaction.py` (the
  process-wide log filter). These already pass settings down: `build_collectors(settings)`,
  `build_sources(settings)`, `run_sources(..., max_miles=...)`,
  `retry_failed_geocodes(retry_hours=..., batch=...)`.
- **Inside pipeline and handler code**, which is what this change removes:
  - `app/events/ingest.py:60` `purge_blocked_tags` reads `blocked_tags`.
  - `app/events/ingest.py:180` `upsert_raw_events` reads `blocked_tags`, and `:206` reads
    `get_settings().center` inside the per-event loop, although the same function already takes
    `max_miles` as a parameter.
  - `app/news/clustering.py:240` `recluster` reads `news_story_window_days`.
  - `app/weather/service.py:60` `WeatherService.get_current` reads the whole object per call.
  - `app/api/news.py:33`, `app/api/events.py:63`, `app/api/root.py:20` read it in the handler body.

The tests show the cost. `tests/test_events_ingest.py:396-446` monkeypatches
`events_blocked_tags` on the cached `Settings` instance (and `blocked_tags` is a property computed
from it, so this only works because the instance is shared). `tests/test_weather.py:36-48` sets
`AIRNOW_API_KEY` and calls `get_settings.cache_clear()` before and after every test so a developer's
`.env` key can't leak into the NWS tests. `tests/test_api_events.py:177` patches
`app.events.refresh.get_settings`, which is reasonable because `refresh()` is a composition root.

`grep -rnE "datetime\.now\((dt\.)?timezone\.utc\)" app` finds 23 calls. Only
`app/events/sources/chattzoo.py` can be pinned (`_now()` at line 242, `parse_occurrence(text, now)`).
The test-isolation requirement "Tests do not depend on the date they run" offers "pass a fixed now
into the code under test" as one of two options, but no DB-backed pipeline function accepts one.
`fix-reconcile-test-dates` (archived 2026-11-07) considered an injectable `now` on
`reconcile_events()` and rejected it *for that change* because it only needed three test dates
fixed. `clamp-future-article-dates` worked by capping against `fetched_at` carried in the row data,
which is already injectable.

The clock call sites fall into three groups:

| Group | Sites | Treatment |
|---|---|---|
| Pipeline logic that filters or ages data | `reconcile_events` (`ingest.py:330`), `retry_failed_geocodes` cutoff and stamps (`:399`, `:412`), `_geocode` cache stamp (`:96`, via `upsert_raw_events`), `recluster` (`clustering.py:239`), `get_stories` (`stories.py:77`), timeseries `ingest` (`app/ingest.py:113`) | inject `now` |
| Records of real I/O | news fetcher `fetched_at` / fallback `published` / `last_fetch` (`fetcher.py:50,110,200,234,290`), scheduler `next_run_time` and `last_run_at` (`scheduler.py`), source fetch windows (`cityspark.py:229`, `tribe.py:127`, `chattzoo.py:244`) | leave on the wall clock |
| HTTP handlers | `api/events.py:76` upcoming filter, `api/timeseries.py:77` `closed_within` cutoff, weather AQI age (`weather/service.py:107`) | leave on the wall clock |

## Goals / Non-Goals

**Goals:**

- Every pipeline function that filters, ages or stamps stored data by the current time accepts an
  injected `now`, so DB tests can pin time instead of computing dates around the real clock.
- Pipeline and handler code receives the setting values it uses; `get_settings()` is called only at
  composition roots and in router dependencies.
- Tests vary a setting by passing a value or a locally built `Settings`, never by mutating the
  cached instance or the environment (except where the code under test is itself a composition root,
  such as `refresh()` or the redaction filter).
- No change to what the running app does, apart from the timestamp detail in Risks.

**Non-Goals:**

- A clock abstraction, a DI container, or a time-freezing test dependency.
- Injecting time into HTTP handlers, the news fetcher, the scheduler or event-source `fetch()`.
- Removing `get_settings()` or its cache, or changing how settings load.
- Restructuring `upsert_raw_events` / `reconcile_events` (that is `decompose-events-upsert`).
- Enforcing the boundary with a lint rule (left to `tighten-python-tooling`, see Open Questions).

## Decisions

### D1. `now: datetime | None = None`, keyword-only, resolved once

Each affected function gains a keyword-only `now` and starts with
`if now is None: now = datetime.now(timezone.utc)`. Every time comparison and stamp inside the call
uses that one value. `run_sources` forwards its `now` to `upsert_raw_events`. The value must be
timezone-aware; callers pass UTC.

Alternatives considered:

- **A `Clock` protocol or class** (`clock.now()`), injected or module-level. Rejected: every consumer
  needs one value per call, not a source of readings, so an object adds a type and a fake for no
  gain. The only thing a callable would preserve is a per-row wall-clock stamp in
  `retry_failed_geocodes`, which nothing depends on (see Risks).
- **`freezegun` / `time-machine`.** Rejected for the same reason `fix-reconcile-test-dates`
  rejected it: a new test dependency that patches `datetime` globally and silently stops working if
  a module changes how it imports `datetime`.
- **Module-level `_now()` seams like the zoo source's.** Rejected for pipeline functions: tests
  would monkeypatch a module attribute, which is the global-mutation pattern this change removes.
  The zoo seam stays; it is already covered by `parse_occurrence(text, now)`.
- **Resolving `now` once per refresh cycle and threading it through `refresh()`.** Not done: each
  function resolving its own default keeps callers unchanged, and a cycle-wide `now` would make
  `reconcile_events` (which runs after network-bound geocode retries) slightly stale. Callers may
  still pass one value to several functions when they want to.

### D2. Which clock sites get `now`

Only the first group in the Context table. The criterion is "the function's output or stored
state depends on now, and DB tests exercise it": `upsert_raw_events` (geocode-cache stamp, used by
the retry cutoff), `run_sources` (forwards), `reconcile_events`, `retry_failed_geocodes`,
`recluster`, `get_stories`, and timeseries `ingest`.

Left alone, with reasons:

- **News fetcher.** `fetched_at`, the missing-date fallback for `published`, and `last_fetch`
  record when network I/O happened. A cycle-wide `now` passed into `fetch_all` would stamp later
  feeds with an earlier time and, through the `clamp-future-article-dates` cap
  (`published = min(published, fetched_at)`), could pull real publish times back. The clamp is
  already testable through `upsert_articles` row data.
- **Scheduler.** `next_run_time=now` means "run immediately"; `last_run_at` records a run.
- **Event-source `fetch()` windows.** Injecting time would change the `EventSource` interface for
  every source. Parsers are where date logic lives, and the zoo parser already takes `now`.
- **HTTP handlers.** A request carries no time; a `Depends(get_now)` seam would exist only for
  tests, and the router tests already compute dates relative to now, which the test-isolation
  requirement allows. `get_stories` gains `now`, but the stories router doesn't pass one.
- **Weather AQI age.** In-memory cache logic mixing `time.monotonic()` and wall-clock observation
  times; its tests already build observation times relative to now.

### D3. Pass setting values into pipeline functions, not the `Settings` object

| Function | New parameter(s) | Supplied by |
|---|---|---|
| `purge_blocked_tags(session, blocked)` | `blocked: Collection[str]` (required) | `main.py` lifespan: `get_settings().blocked_tags` |
| `upsert_raw_events(..., *, blocked_tags, center, now)` | `blocked_tags: Collection[str] = frozenset()`, `center: Coords \| None = None` | `run_sources` |
| `run_sources(..., *, blocked_tags, center, now)` | same, forwarded | `events/refresh.py`: `settings.blocked_tags`, `settings.center` |
| `recluster(session, *, window_days, now)` | `window_days: int` (required) | `news/refresh.py`: `get_settings().news_story_window_days` |

Builders that read many fields (`build_sources`, `build_collectors`) keep taking `Settings`; that
convention stays. Pipeline functions take values because they use one or two fields each, and a
test then passes `blocked_tags={"food"}` instead of building a full `Settings`.

Alternative considered: pass `settings: Settings` everywhere, as the builders do. Rejected for
pipeline functions: it hides which fields are read and still makes every test construct a
`Settings`. A small `IngestPolicy` dataclass grouping `max_miles`, `center` and `blocked_tags` was
also considered; it is a reasonable shape, but grouping `upsert_raw_events`'s parameters belongs to
`decompose-events-upsert`. If that change introduces such an object, use it instead of loose
keywords.

**Defaults.** `upsert_raw_events` / `run_sources` default to "no blocklist" and "no center",
matching the existing `max_miles=0` ("filter off") default, so the ~30 existing test call sites
don't change. Calling with `max_miles > 0` and no `center` raises `ValueError` rather than
falling back to the configured center, which would bring the global back. `purge_blocked_tags` and
`recluster` have one production caller each, so their new parameters are required.

### D4. Routers take settings through `Depends(get_settings)`

`get_stories`, `items` and `config` gain `settings: Settings = Depends(get_settings)`, in the same
style as the existing `session: AsyncSession = Depends(get_session)`. Request behaviour is
identical: `get_settings` is cached, and FastAPI resolves it per request. Tests that call these
handlers directly (`tests/test_news_db.py`, `tests/test_api_events.py`) pass `settings=` explicitly;
an HTTP-level test can use `app.dependency_overrides[get_settings]`.

### D5. `WeatherService(settings: Settings | None = None)`

The service stores an optional `Settings` and `get_current()` uses
`self._settings or get_settings()`. The module singleton `service = WeatherService()` keeps resolving
the process settings lazily, on first use, so this change adds no settings read at import time
(`extract-spa-serving` is weighing import-time side effects). Tests construct
`WeatherService(make_settings(airnow_api_key=""))` and drop the autouse env/`cache_clear` fixture.
An explicit `airnow_api_key` keyword overrides both the environment and `.env`, which is the
protection that fixture gave.

### D6. Composition roots, and what stays global

`get_settings()` stays in `app/db.py`, `app/main.py`, `app/scheduler.py`, `app/events/refresh.py`,
`app/news/refresh.py` (new: it now reads the story window to pass to `recluster`),
`app/weather/service.py` (singleton fallback only), router dependencies, and `app/redaction.py`.
Redaction stays global on purpose: the log filter is installed once per process and must mask the
live process's secrets, so `tests/test_redaction.py` correctly sets the environment and clears the
cache. The review flagged that test as a symptom; it isn't one, and it is not changed.
`tests/test_api_events.py:177` (patching `app.events.refresh.get_settings`) also stays: `refresh()`
is a composition root.

### D7. A `make_settings()` test helper

`tests/conftest.py` gains `make_settings(**overrides) -> Settings`, returning
`Settings(_env_file=None, **overrides)`, so tests build an isolated settings object in one call.
`DATABASE_URL` still comes from the environment that `conftest.py` sets, so the temporary database
is unaffected.

### D8. Spec placement: `test-isolation` only

The `events`, `news`, `weather` and `timeseries` specs describe behaviour that doesn't change. What
changes is a property tests rely on: code under test accepts a fixed `now` and its configuration as
inputs. The delta modifies "Tests do not depend on the date they run" (the inject-a-fixed-now route
becomes real and is shown in a scenario) and adds one requirement about varying configuration
without global mutation.

## Sibling changes and landing order

This is item 6 of 13 in the suggested order. Overlaps:

- **`ingest-owns-entity-status` (1)** and **`move-timeseries-into-package` (3)** both touch timeseries
  `ingest` in `app/ingest.py`; (3) moves it to `app/timeseries/ingest.py`. Land after both and add
  `now` at whatever path exists. The change to `ingest` is one parameter and one line.
- **`add-shared-http-client` (2)** replaces `WeatherService._make_client` / `_transport`. This change
  only touches the constructor and `get_current`'s settings line, so the textual conflict is small.
- **`unify-refresh-orchestration` (4)** makes each feature own its refresh cycle. Those cycles are
  the composition roots here: wherever they end up, they read settings once and pass values down.
  If (4) lands first, put the new `blocked_tags` / `center` / `window_days` arguments in its
  feature-owned refresh functions.
- **`decompose-events-upsert` (5)** splits `upsert_raw_events` / `reconcile_events`, the same code
  this change adds parameters to. **Recommend (5) lands first**, then this change threads `now`,
  `blocked_tags` and `center` through the decomposed helpers (and adopts any policy object (5)
  introduces, per D3). Doing it the other way round means (5) rebases every helper signature.
- **`consolidate-shared-helpers` (7)** owns CSV-setting parsing on `Settings`. `blocked_tags` is
  already a `Settings` property; this change only moves where it is read. If (7) renames it, follow
  the rename.
- **`add-typed-contracts` (8)** adds response models to the same three routers. It conflicts only
  textually with the new `settings` parameter.
- **`extract-spa-serving` (10)** may introduce an app factory. `main.py`'s `get_settings()` calls
  stay composition-root reads either way; D5 avoids adding a new import-time read.
- **`tighten-python-tooling` (11)** could enforce the D6 boundary with a ruff
  `flake8-tidy-imports` banned-API rule plus per-file ignores for the composition roots. Not done
  here; see Open Questions.

## Risks / Trade-offs

- **[Observable] Geocode stamps use one `now` per call.** `retry_failed_geocodes` stamps every
  retried row with the pass's `now` instead of a per-row reading, and `upsert_raw_events` stamps new
  geocode-cache rows with its batch `now`. With the geocoder throttled to about one request per
  second, a pass of `events_geocode_retry_batch` rows used to spread stamps over that many seconds.
  Rows retried together now tie on `last_attempted_at`, so their relative order in the next
  oldest-first pass is arbitrary among themselves. Retry eligibility is measured in hours
  (`events_geocode_retry_hours`), so no row becomes eligible meaningfully earlier or later.
  Mitigation: `.order_by(GeocodeCache.last_attempted_at, GeocodeCache.address)` makes ties
  deterministic.
- **[Observable to direct callers only] Neutral defaults.** `upsert_raw_events` / `run_sources`
  without `blocked_tags` no longer apply the configured blocklist. The app always calls through
  `refresh()`, which passes it. No existing test relies on the default `topics` blocklist being
  applied at ingest. → Covered by a refresh-level test that `refresh()` forwards the configured
  blocklist and center.
- **[Risk] Parameter growth on `upsert_raw_events` / `run_sources`.** Seven parameters is a lot. →
  All new ones are keyword-only with defaults, and D3 points at grouping them in
  `decompose-events-upsert`.
- **[Risk] A future pipeline function reaches for `get_settings()` again.** → `AGENTS.md` states
  the boundary; a lint rule is an open question.
- **[Risk] A test passes a naive `now`.** Comparing it with aware DB timestamps raises a
  `TypeError` (or a Postgres comparison error) at once, so it can't pass silently.

## Migration Plan

Code-only refactor; no schema, configuration or deployment steps. Rollback is a revert.

## Open Questions

- Should `tighten-python-tooling` add a banned-API rule so `get_settings` can only be imported by
  the composition-root modules? Cheap to add after both changes land; this change doesn't depend
  on it.
- Should `center` be required on `upsert_raw_events` whenever `max_miles > 0` (the D3
  `ValueError`), or always required? The `ValueError` keeps existing tests unchanged; making it
  required is stricter but touches every call site.
- Is the news fetcher worth a per-feed `now` on `fetch_feed` (not `fetch_all`) for a future test of
  the missing-date fallback? Left out because no current test needs it.
