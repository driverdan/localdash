## 1. Logger names (`logging.getLogger(__name__)`)

- [x] 1.1 Replace every hand-written `logging.getLogger("localdash...")` under `app/` with `logging.getLogger(__name__)`. On current `main` there are 14: ten in `app/events/` (`geocoding.py`, `ingest.py`, `refresh.py`, `sources/__init__.py`, `sources/carcruisefinder.py`, `sources/chattzoo.py`, `sources/cityspark.py`, `sources/ical.py`, `sources/meetup.py`, `sources/tribe.py`), plus `app/news/fetcher.py`, `app/news/refresh.py`, `app/scheduler.py` and `app/weather/service.py`. Use the paths as they are after any sibling changes that moved or split these files
- [x] 1.2 Confirm `grep -rn 'getLogger("' app` finds nothing, and that no logger was added to a module that does not log (collectors, `app/ingest.py`)
- [x] 1.3 `tests/test_events_tribe.py`: change the `caplog.at_level(..., logger="localdash.events")` in `test_event_without_utc_start_is_skipped_and_parse_continues` to `logger="app.events.sources.tribe"`, and the one in `test_build_sources_skips_malformed_entries_loudly` to `logger="app.events.sources"`. In each test, also assert that the warning record's `name` is that logger, so a stale name fails instead of passing through root propagation
- [x] 1.4 Grep `tests/` for any other `localdash.<feature>` logger reference and update it. `tests/test_redaction.py`'s private `localdash.test` logger can stay; it names no app module

## 2. WebSocket handler cleanup (`app/api/root.py`)

- [x] 2.1 Rewrite `ws_live` so that, after `manager.connect(ws)`, the receive loop runs inside `contextlib.suppress(Exception)` in a `try` block, and the `finally` calls `await manager.disconnect(ws)` once (design decision 2). Remove the two `except` branches, the `# noqa: BLE001` comment if it is still there, and the unused `WebSocketDisconnect` import
- [x] 2.2 `tests/test_api_routes.py`: add a test that opens `/api/v1/ws` with a `TestClient` (no lifespan), closes it, and then asserts that `app.ws.manager` no longer holds any client. Clear or snapshot `manager._clients` so other tests cannot affect it

## 3. Remove `MEETUP_RADIUS_MILES`

- [x] 3.1 Delete `MEETUP_RADIUS_MILES` and its comment from `app/events/__init__.py`. Keep the module docstring and the shared-center comment
- [x] 3.2 `app/events/sources/__init__.py`: drop the import and the `radius_miles=MEETUP_RADIUS_MILES` argument in `build_sources()`
- [x] 3.3 `app/events/sources/meetup.py`: put the comment "Meetup keywordSearch radius; not config — matches the PoC default" on the `radius_miles: int = 50` default
- [x] 3.4 `tests/test_events_meetup.py`: extend `test_build_sources_includes_meetup_only_when_token_set` (or add a test) to assert that the built `MeetupSource` has `radius_miles == 50`
- [x] 3.5 Confirm that `grep -rn MEETUP_RADIUS_MILES app tests` finds nothing

## 4. Module-level parsers for iCal and Meetup

- [x] 4.1 `app/events/sources/ical.py`: move `ICalSource.parse` to module-level `parse_calendar(ics_bytes: bytes, source_name: str, feed_url: str) -> list[RawEvent]`, replacing `self.name` with `source_name` and `self.url` with `feed_url`. `ICalSource.fetch` calls `parse_calendar(resp.content, self.name, self.url)`. Remove the method
- [x] 4.2 `app/events/sources/meetup.py`: move `MeetupSource.parse` to module-level `parse_payload(payload: dict, source_name: str, fallback_url: str) -> list[RawEvent]`, replacing `self.name` with `source_name` and `self.endpoint` with `fallback_url`. `MeetupSource.fetch` calls `parse_payload(resp.json(), self.name, self.endpoint)`. Remove the method
- [x] 4.3 `tests/test_events_ical.py`: import `parse_calendar` and replace each `_source().parse(X)` with `parse_calendar(X, <name>, <url>)`, using the values `_source()` used (keep the existing assertions, including any on `source_name` and `source_url`). Drop `_source()` if nothing else uses it
- [x] 4.4 `tests/test_events_meetup.py`: import `parse_payload` and replace each `_source().parse(X)` with `parse_payload(X, "Meetup", ENDPOINT)`. Keep `_source()` only if the registration tests still need it
- [x] 4.5 Confirm that no `def parse(self` remains under `app/events/sources/` and that no caller of `.parse(` on a source is left (`grep -rn "\.parse(" app tests`)

## 5. Documentation

- [x] 5.1 `AGENTS.md`: add a short note, for example under "Non-obvious decisions", that modules log via `log = logging.getLogger(__name__)`. Logger names are module paths (`app.events.sources.tribe`) and appear in log output through `main.py`'s `basicConfig` format. Hand-written `localdash.*` names are not used
- [x] 5.2 `AGENTS.md` events feature `sources/` bullet: state that each source keeps its pure parsing in module-level functions (e.g. `parse_page`, `parse_payload`, `parse_calendar`, `parse_listing`), which take what they need as arguments and which `fetch()` calls and tests import directly
- [x] 5.3 In the implementation PR description, call out the logger-name change in log output (`localdash.events` becomes `app.events.<module>`, and so on) for anyone with saved log searches

## 6. Verification

- [x] 6.1 `pytest` passes in full
- [x] 6.2 `ruff check` and `ruff format --check` pass on the changed files, as do the pre-commit hooks
- [x] 6.3 Run the app (`docker compose up --build`) and check that an events or news refresh logs lines under `app.events.*` / `app.news.*`, and that opening and closing the dashboard tab logs no WebSocket error
