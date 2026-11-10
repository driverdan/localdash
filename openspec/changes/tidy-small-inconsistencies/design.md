## Context

Four independent cleanups from the Python architecture review, each confirmed against `origin/main`:

1. **Logger names.** 14 module loggers, all hand-written strings:
   - all ten in `app/events/` (`geocoding.py`, `ingest.py`, `refresh.py`, and seven modules in
     `sources/`) use `localdash.events`;
   - `app/news/refresh.py:18` uses `localdash.news` and `app/news/fetcher.py:41` uses
     `localdash.news.fetcher`;
   - `app/scheduler.py:28` uses `localdash.scheduler` and `app/weather/service.py:29` uses
     `localdash.weather`;
   - `app/collectors/` and `app/ingest.py` do not log at all.

   Logging is configured only by `logging.basicConfig(level=logging.INFO)` in `app/main.py`. Its
   default format, `%(levelname)s:%(name)s:%(message)s`, prints the logger name on every line.
   There is no `dictConfig`, uvicorn `--log-config`, or compose logging driver. `alembic.ini` only
   configures `root`, `sqlalchemy.engine` and `alembic`. `app/redaction.py` wraps the record
   factory globally and ignores logger names. In `tests/`, the only references to these names are
   two `caplog.at_level("WARNING", logger="localdash.events")` calls in `tests/test_events_tribe.py`
   (lines 109 and 245). `tests/test_redaction.py` makes its own `localdash.test` logger, which no
   app module uses. `tests/test_weather.py` uses `caplog.set_level` without a logger name. The
   `localdash.news` / `localdash.events` strings in the frontend specs are `localStorage` keys and
   unrelated.
2. **`app/api/root.py:32-35`**: `except WebSocketDisconnect` and `except Exception  # noqa: BLE001`
   both run only `await manager.disconnect(ws)`. Together they swallow every `Exception`.
   `ConnectionManager.disconnect` is a lock-guarded `set.discard`, so it is idempotent.
3. **`app/events/__init__.py:17`** `MEETUP_RADIUS_MILES = 50` is imported once
   (`app/events/sources/__init__.py:23`, used at `:76`). It repeats `MeetupSource.__init__`'s
   `radius_miles: int = 50` default (`meetup.py:103`). Nothing else references it.
4. **Parser placement.** `ICalSource.parse` (`ical.py:76`) reads `self.name` and `self.url`.
   `MeetupSource.parse` (`meetup.py:141`) reads `self.name` and `self.endpoint`. The other four
   sources use module-level functions that take what they need as arguments:
   - tribe: `parse_page(payload, source_name)`;
   - cityspark: `parse_payload(payload)`;
   - carcruisefinder: `parse_listing(html, listing_url)`;
   - chattzoo: `parse_listing`, `parse_detail`.

   The tests for those four import and call the functions. `tests/test_events_ical.py` and
   `tests/test_events_meetup.py` build a throwaway source (`_source().parse(...)`) only to reach
   the method. `EventSource` declares only `fetch()`, so `parse` is not part of any interface.

## Goals / Non-Goals

**Goals:**

- Each item reads one way across the codebase, and `AGENTS.md` says which way for the two that are
  conventions (loggers and parsers).
- No behaviour change apart from the logger names that item 1 renames on purpose.

**Non-Goals:**

- Adding loggers to modules that do not log today (collectors, `app/ingest.py`). Under the new
  convention a module that needs one adds `log = logging.getLogger(__name__)`. Adding an unused
  logger now is dead code.
- Changing log format, levels, or handlers. A structured or named-format logging setup is a
  separate decision.
- Removing the stale `# noqa: BLE001` comments repo-wide or adding lint rules. That is
  `tighten-python-tooling`.
- Deduplicating `_to_aware_utc` and other helpers that `ical.py`, `meetup.py` and
  `carcruisefinder.py` each define. That is `consolidate-shared-helpers`.

## Decisions

### 1. `logging.getLogger(__name__)` everywhere

Options considered:

- **Per-module `__name__` (chosen).** This is the standard library's documented idiom. The name
  cannot drift from the module path, and nothing needs to be maintained by hand. The hierarchy
  still allows feature-wide control (`logging.getLogger("app.events").setLevel(...)` covers every
  events module, as `localdash.events` does today) and adds per-module control. When
  `unify-refresh-orchestration` creates new modules, their logger names follow automatically.
- **A consistent hand-written `localdash.<feature>.<module>` scheme.** This keeps the `localdash`
  brand in log lines. It is the same idea as `__name__` with a different root, but every new or
  moved module needs a string kept in sync by hand, and that bookkeeping is how the current names
  drifted. Rejected.
- **Leave it.** The cost of the current state is real but small: you cannot tell which events
  module logged a line, and new modules have no rule to follow. With only two test call sites and
  no runtime consumers, fixing it is cheap. Rejected.

**Observable effect:** log lines change from, for example, `WARNING:localdash.events:...` to
`WARNING:app.events.sources.tribe:...`, and from `INFO:localdash.scheduler:...` to
`INFO:app.scheduler:...`. Release notes or the PR description should mention this for anyone with
saved log searches. The repo itself has none.

The two `caplog` calls in `tests/test_events_tribe.py` change to the precise emitting logger.
Line 109 tests `parse_page`, so it uses `app.events.sources.tribe`. Line 245 tests
`build_sources`, so it uses `app.events.sources`. A stale name would still pass, because WARNING
records propagate to root, where caplog's handler sits. Tests that read the logger name therefore
also need to read `record.name`, so the rename is actually checked (see tasks).

### 2. WebSocket handler: `try`/`finally` around a suppressed receive loop

```python
await manager.connect(ws)
try:
    # A client close (WebSocketDisconnect) or a broken socket ends the session;
    # neither is an error worth surfacing.
    with contextlib.suppress(Exception):
        while True:
            await ws.receive_text()
finally:
    await manager.disconnect(ws)
```

A bare `try`/`finally` with no suppression was rejected because it changes behaviour.
Non-disconnect exceptions would propagate out of the endpoint into Starlette and uvicorn's error
handling, where today they are silently absorbed. `contextlib.suppress(Exception)`
keeps today's "swallow everything" exactly and avoids a `try`/`except`/`pass` that common lint
rules (`SIM105`, `S110`) flag if `tighten-python-tooling` enables them. A single
`except Exception: await manager.disconnect(ws)` would also preserve behaviour, but `finally` is
what the review asked for, and it also deregisters the socket when the task is cancelled
(`CancelledError` is a `BaseException`, so neither current branch catches it). That only happens at
server shutdown, when the set is about to be discarded anyway. The difference is not observable,
and it is the correct cleanup.

### 3. Delete `MEETUP_RADIUS_MILES`; the constructor default is the one value

`build_sources()` stops passing `radius_miles`, and `MeetupSource`'s `radius_miles: int = 50`
default keeps the comment "Meetup keywordSearch radius; not config — matches the PoC default." The
module docstring's comment about the shared center stays in `app/events/__init__.py`, which is
then only a docstring and that comment. Promoting the radius to a setting would be a feature
change, so it is not done here. A new test pins the built source's `radius_miles == 50` so the
default cannot change silently.

### 4. Module-level parse functions, not methods

Four of six sources already use module-level functions, and every one of their tests calls them
that way. The `events` spec and `AGENTS.md` already talk about "the source's pure parse function".
Moving the two methods out is the smaller change, and it makes the parsers testable without a
constructed source. A Meetup source needs a token to construct.

- `ical.py`: `parse_calendar(ics_bytes: bytes, source_name: str, feed_url: str) -> list[RawEvent]`.
  `feed_url` is the `source_url` fallback for components without a `URL`. `ICalSource.fetch`
  calls `parse_calendar(resp.content, self.name, self.url)`.
- `meetup.py`: `parse_payload(payload: dict, source_name: str, fallback_url: str) ->
  list[RawEvent]`. `MeetupSource.fetch` calls `parse_payload(resp.json(), self.name,
  self.endpoint)`. The name matches cityspark's `parse_payload`. Both are module-scoped, so they
  do not collide.

Arguments are explicit and required, as in tribe's `parse_page(payload, source_name)`. The methods
are removed, not kept as delegates: nothing outside the tests calls them.

Collectors are not affected. `BaseCollector.normalize()` is an abstract interface method, which is
a different contract from an event source's private parse helper. `AGENTS.md` keeps describing
collectors as implementing `normalize()`.

### 5. Spec deltas

Nothing here changes product behaviour. The repo puts internal conventions in two places:
`AGENTS.md`, which is covered by `project-documentation`'s "AGENTS.md matches the shipped app",
and `code-quality-tooling`, which is about the pre-commit and lint machinery, not code style. So:

- `project-documentation`: add a scenario to "AGENTS.md matches the shipped app" requiring the
  two conventions to be stated. That is where a future agent looks before adding a module.
  `contributor-documentation` was considered and rejected, because its requirements send code
  conventions to `AGENTS.md`.
- `live-updates`: add a "Closed client is removed" scenario to the existing endpoint requirement,
  without changing its text. It pins the behaviour item 2 must keep, and the new test backs it.
- Items 3 and 4 have no spec delta. The events spec says the Meetup source is "filtered to a
  50-mile radius" and mentions "the source's pure parse function", and both stay true.

### Overlap with sibling review changes (landing order 1-13; this change is 13, last)

- `add-shared-http-client` (2) rewrites every event source's `fetch`, including `ical.py` and
  `meetup.py`. This change edits the line in those `fetch` bodies that calls the parser. Rebase
  onto it: keep its client code and change only the parse call.
- `extract-orm-base` (3, formerly `move-timeseries-into-package`) no longer moves any files, so
  `app/scheduler.py` keeps its path and there is no overlap.
- `unify-refresh-orchestration` (4) rewrites `app/scheduler.py`, `app/events/refresh.py` and
  `app/news/refresh.py`. Convert whatever logger lines those files have at implementation time, and
  any new modules it adds.
- `decompose-events-upsert` (5) splits `app/events/ingest.py`. Any new module it creates gets
  `__name__`.
- `inject-settings-and-clock` (6) may touch `build_sources()` and Meetup construction. Item 3
  only removes one keyword argument, so take its version and drop `radius_miles=` if it is still
  there.
- `consolidate-shared-helpers` (7) dedupes helpers in `ical.py`, `meetup.py` and
  `carcruisefinder.py` next to the parsers this change moves. Move the parser bodies as they stand
  after it lands.
- `tighten-python-tooling` (11) removes the stale `# noqa: BLE001` on `app/api/root.py:34`. Item
  2 deletes that line anyway. If this change lands first, the tooling change has one fewer comment
  to remove. If it adds lint rules, the item-2 shape above already satisfies the likely ones.
- `extract-spa-serving` (10) moves code out of `app/main.py`. If `logging.basicConfig` moves with
  it, the observable-name note in decision 1 still holds.

No sibling depends on this change.

## Risks / Trade-offs

- [Someone has saved log searches or alerts on `localdash.*` logger names] → None exist in the
  repo. Call out the rename in the implementation PR description.
- [`caplog` tests keep passing against a stale logger name, because WARNING propagates to root
  regardless] → Assert `record.name` in the two tribe tests, so a future rename breaks them.
- [Merge conflicts with sibling changes that touch the same files] → This change lands last.
  Every edit is a one-line substitution, or a function move that is easy to reapply on rebase.
- [Item 4 is the most debatable of the four (pure consistency churn across two sources and two
  test files)] → It is cheap and already the majority style. If reviewers prefer, it can be
  dropped from the bundle without affecting the other three.

## Open Questions

- Should log lines keep a `localdash` brand? If the user wants that, the alternative is
  `getLogger(__name__)` plus a `basicConfig` format string that carries a fixed prefix, not
  hand-written names. This proposal assumes the brand is not needed.
