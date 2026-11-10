## 0. Before starting

- [x] 0.1 Check which sibling changes have landed (`decompose-events-upsert`,
  `unify-refresh-orchestration`, `ingest-owns-entity-status`,
  `add-shared-http-client`) and apply the tasks below to the current function names and paths
  (see design.md "Sibling changes and landing order")
- [x] 0.2 Re-run `grep -rn "get_settings" app` and
  `grep -rnE "datetime\.now\((dt\.)?timezone\.utc\)" app` and confirm the call sites still match
  design.md's Context table

## 1. Test helper

- [x] 1.1 Add `make_settings(**overrides) -> Settings` to `tests/conftest.py` (below the
  `DATABASE_URL` override block), returning `Settings(_env_file=None, **overrides)`

## 2. Events: settings values and `now`

- [x] 2.1 `purge_blocked_tags(session, blocked)`: take the blocklist as a required argument and
  drop the `get_settings()` call; update the `app/main.py` lifespan call to pass
  `get_settings().blocked_tags`
- [x] 2.2 `upsert_raw_events`: add keyword-only `blocked_tags: Collection[str] = frozenset()`,
  `center: Coords | None = None`, `now: datetime | None = None`; resolve `now` once at the top;
  use `center` for the radius check (raise `ValueError` when `max_miles > 0` and `center` is
  None); pass `now` to `_geocode` for the `last_attempted_at` stamp
- [x] 2.3 `run_sources`: add the same three keyword-only parameters and forward them
- [x] 2.4 `reconcile_events(session, *, now=None)`: use the resolved `now` in the upcoming filter
- [x] 2.5 `retry_failed_geocodes(..., now=None)`: use the resolved `now` for the cutoff and for each
  row's `last_attempted_at`; add `GeocodeCache.address` as a secondary `order_by` key so tied
  stamps retry in a stable order
- [x] 2.6 Remove the `get_settings` import from `app/events/ingest.py`
- [x] 2.7 `app/events/refresh.py`: pass `blocked_tags=settings.blocked_tags` and
  `center=settings.center` to `run_sources`

## 3. News: settings values and `now`

- [x] 3.1 `recluster(session, *, window_days, now=None)`: take the window as a required keyword,
  use the resolved `now`, and remove the `get_settings` import from `app/news/clustering.py`
- [x] 3.2 `app/news/refresh.py`: read `get_settings().news_story_window_days` and pass it to
  `recluster`
- [x] 3.3 `get_stories(session, hours, limit, *, now=None)` in `app/news/stories.py`: use the
  resolved `now` for the cutoff

## 4. Timeseries and weather

- [x] 4.1 Timeseries `ingest(session, source_key, observations, *, now=None)` (`app/ingest.py`):
  replace the `datetime.now` line with the resolved `now`
- [x] 4.2 `WeatherService.__init__(self, settings: Settings | None = None)`: store it; in
  `get_current` use `self._settings or get_settings()`; keep the module singleton
  `service = WeatherService()` (no import-time settings read)

## 5. Routers

- [x] 5.1 `app/api/news.py` `get_stories`: add `settings: Settings = Depends(get_settings)` and use
  it for the window clamp
- [x] 5.2 `app/api/events.py` `items`: add `settings: Settings = Depends(get_settings)` and use
  `settings.center` as the default origin
- [x] 5.3 `app/api/root.py` `config`: add `settings: Settings = Depends(get_settings)`
- [x] 5.4 Confirm `grep -rn "get_settings()" app` now lists only the composition roots named in
  design.md D6

## 6. Tests

- [x] 6.1 `tests/test_events_ingest.py` blocklist tests: pass `blocked_tags=` to
  `upsert_raw_events` and `blocked=` to `purge_blocked_tags` instead of monkeypatching
  `get_settings()`; rewrite `test_blocked_tags_normalizes_names` against
  `make_settings(events_blocked_tags=" Politics , , MUSIC ")`
- [x] 6.2 `tests/test_events_ingest.py` radius tests (those passing `max_miles=100`): pass
  `center=`; replace the `get_settings().center` read at the Memphis-distance test with a
  `CENTER` constant or `make_settings().center`; add a test that `max_miles > 0` without `center`
  raises `ValueError`
- [x] 6.3 Add a reconcile test with a fixed `now`: two duplicates on a fixed past date merge with
  `now` before that date and do not merge with `now` after it
- [x] 6.4 Add a geocode-retry test with a fixed `now`: a failed cache row stamped at a fixed time is
  retried at `now = stamp + 25h` (and its `last_attempted_at` becomes `now`) and skipped at
  `now = stamp + 23h`, with `retry_hours=24`
- [x] 6.5 Add a test that `refresh()` forwards the configured blocklist and center to
  `run_sources` (patch `app.events.refresh.get_settings` as
  `test_refresh_endpoint_reports_counts` already does, and capture `run_sources`'s arguments)
- [x] 6.6 `tests/test_weather.py`: delete the autouse `_pin_airnow_key` fixture and
  `_set_airnow_key`; construct services with `WeatherService(make_settings(airnow_api_key=""))`,
  or with `"test-key"` for the AQI tests
- [x] 6.7 `tests/test_news_db.py`: pass `settings=make_settings()` in the direct
  `api_get_stories(...)` calls, and `window_days=` wherever `recluster` is called; add one
  `get_stories(..., now=...)` test showing the cutoff follows the injected `now`
- [x] 6.8 `tests/test_api_events.py`: pass `settings=make_settings()` in the direct `items(...)`
  calls; leave the `app.events.refresh.get_settings` patch at line 177 as is
- [x] 6.9 `tests/test_live_signals.py`: let `fake_recluster` accept the new keyword arguments
  (`**kwargs`)
- [x] 6.10 Leave `tests/test_redaction.py` unchanged (design.md D6)

## 7. Documentation

- [x] 7.1 `AGENTS.md` Tests section: extend the "inject a fixed now" sentence to name the `now`
  keyword on the events, news and timeseries pipeline functions; add that tests vary configuration
  by passing values or `make_settings(...)`, not by mutating `get_settings()` or the environment
  (redaction and refresh-cycle tests excepted)
- [x] 7.2 `AGENTS.md` Config section: one or two sentences saying `get_settings()` is read at
  composition roots (refresh cycles, scheduler, lifespan/`main.py`, `db.py`, redaction, router
  `Depends`) and pipeline functions receive values as arguments
- [x] 7.3 Update docstrings of the changed functions to describe `now` and the new parameters

## 8. Verify

- [x] 8.1 `uv run ruff check` and `uv run ruff format --check` on changed files
- [x] 8.2 Run the full `pytest` suite against the dev Postgres (`docker compose up -d db`)
- [x] 8.3 Rebuild and start the app (`docker compose up --build`); confirm one events refresh, one
  news refresh and a weather fetch complete in the logs, and that `/api/v1/config`,
  `/api/v1/news/stories` and `/api/v1/events/items` respond as before
- [x] 8.4 `openspec validate inject-settings-and-clock --strict`
