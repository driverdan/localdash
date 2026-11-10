## Why

A Python architecture review found four small inconsistencies that each cost a reader a moment of
"why is this one different?" and none of which is worth its own change. Logger names are
hand-written strings that have already drifted (ten events modules share one name; news uses two
schemes; collectors have none). The live WebSocket handler says "disconnect" twice. A
package-level constant duplicates a default and is used once. Two of six event sources keep their
pure parser as a method while the other four use module-level functions. Fixing them together, last
in the review's landing order, keeps the churn to one small PR.

## What Changes

All four items are behaviour-preserving refactors. The one externally visible effect is item 1's
logger names in log output.

1. **Loggers use `logging.getLogger(__name__)`.** The 14 module loggers under `app/` switch from
   hand-written `localdash.*` names to their module path (`localdash.events` becomes
   `app.events.ingest`, `app.events.sources.tribe`, and so on; `localdash.news.fetcher` becomes
   `app.news.fetcher`; `localdash.scheduler` becomes `app.scheduler`; `localdash.weather` becomes
   `app.weather.service`). **Observable:** `main.py`'s `logging.basicConfig` prints the logger name
   in every line (`WARNING:app.events.sources.tribe:...` instead of `WARNING:localdash.events:...`).
   Nothing in the repo filters on these names except two `caplog` calls in
   `tests/test_events_tribe.py`, which move to the new name. No logger is added to modules that do
   not log today (collectors, `app/ingest.py`). The convention is recorded in `AGENTS.md`.
2. **`/api/v1/ws` handler cleans up in one place.** The two `except` branches in
   `app/api/root.py:ws_live` that both call `manager.disconnect(ws)` become a single
   `try`/`finally`, with the exception still suppressed so a closed or broken socket never reaches
   the ASGI error log. The now-unused `WebSocketDisconnect` import goes.
3. **`MEETUP_RADIUS_MILES` is removed.** `app/events/__init__.py` stops defining it and
   `build_sources()` stops passing it, so `MeetupSource`'s own `radius_miles=50` default (where the
   "not config; matches the PoC" comment moves) is the single source of the value.
4. **Event-source parsers are module-level functions.** `ICalSource.parse` and `MeetupSource.parse`
   become `parse_calendar(ics_bytes, source_name, feed_url)` in `ical.py` and
   `parse_payload(payload, source_name, fallback_url)` in `meetup.py`, matching tribe
   (`parse_page`), cityspark (`parse_payload`), carcruisefinder (`parse_listing`) and chattzoo
   (`parse_listing`, `parse_detail`). Their tests call the functions directly instead of building a
   source to call a method. The convention is recorded in `AGENTS.md`.

No API, schema, setting, or event-data change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `project-documentation`: "AGENTS.md matches the shipped app" gains a scenario requiring
  `AGENTS.md` to state the two backend conventions this change settles (module-path logger names,
  module-level event-source parse functions), so the next module follows them.
- `live-updates`: "Global live-update WebSocket endpoint" gains a scenario pinning what the
  refactored handler must keep doing: a client that closes its socket is removed from the
  broadcast set. Requirement text is unchanged.

## Impact

- Code: 14 `getLogger` lines under `app/` (`app/events/**`, `app/news/fetcher.py`,
  `app/news/refresh.py`, `app/scheduler.py`, `app/weather/service.py`); `app/api/root.py`;
  `app/events/__init__.py`, `app/events/sources/__init__.py`, `app/events/sources/meetup.py`,
  `app/events/sources/ical.py`.
- Tests: `tests/test_events_tribe.py` (caplog logger name), `tests/test_events_ical.py`,
  `tests/test_events_meetup.py` (direct parser calls, plus a Meetup radius check),
  `tests/test_api_routes.py` (new WebSocket cleanup test).
- Docs: `AGENTS.md`.
- Operations: anyone grepping container logs for `localdash.events` (etc.) needs the new
  `app.` prefixes. No tooling in the repo does.
- Overlaps with sibling review changes that edit the same files; see `design.md`.
