## 1. Config

- [ ] 1.1 Add `events_ingest_max_miles: float = 50` to `app/config.py` beside the other
      `events_*` settings, with a comment stating that a non-positive value disables the
      ingest radius filter

## 2. Ingest filter

- [ ] 2.1 Add a module-level `_haversine_miles(a: Coords, b: Coords) -> float` helper to
      `app/events/ingest.py` (earth radius 3958.8 mi, `math` stdlib only)
- [ ] 2.2 Add a `max_miles: float = 0` keyword to `upsert_raw_events()`; on the new-event
      path, after `_geocode(...)`, when `max_miles > 0` and coords resolved and the haversine
      distance from `CHATTANOOGA_CENTER` (imported from `app.events`) exceeds `max_miles`,
      increment a `skipped_far` counter, log the drop at debug with title and distance, and
      `continue` before any `Event`/tag/link is created (skip the loop-tail link upsert)
- [ ] 2.3 Return `skipped_far` in the stats dict (always present, 0 when disabled) and leave
      the merge branch untouched
- [ ] 2.4 Thread `max_miles: float = 0` through `run_sources()` into `upsert_raw_events()`

## 3. Wiring

- [ ] 3.1 In `app/events/refresh.py`, pass `settings.events_ingest_max_miles` to
      `run_sources()` and add the `skipped_far` count to the summary log line
- [ ] 3.2 Confirm `POST /api/v1/events/refresh` (`app/api/events.py`) needs no change — it
      returns the stats dict verbatim, so `skipped_far` flows through automatically

## 4. Tests (offline, fake geocoder; DB-backed via `events_db_session`, auto-skip like the rest)

- [ ] 4.1 Pure test for `_haversine_miles` (known pair, e.g. Chattanooga→Memphis ≈ 300 mi;
      zero distance for identical points)
- [ ] 4.2 Far new event is dropped: fake geocoder returns Memphis coords; assert no event row,
      no links/tags, and `stats["skipped_far"] == 1`
- [ ] 4.3 Nearby new event passes: fake geocoder returns downtown Chattanooga coords; assert
      created with location and `skipped_far == 0`
- [ ] 4.4 Unlocated events are kept when the filter is on: no-address raw and
      geocode-failure raw are both stored with null location, `skipped_far == 0`
- [ ] 4.5 `max_miles=0` disables the filter: far-geocoding event is stored with its location
- [ ] 4.6 Merge path is exempt: ingest a nearby event, then re-ingest the same canonical key
      from a second source with the filter on; assert it merges (two links, `merged == 1`)
      and is not dropped
- [ ] 4.7 Existing ingest tests still pass unchanged (default `max_miles=0` keeps current
      behavior for callers that do not opt in)

## 5. Validation

- [ ] 5.1 Run `pytest` (with `docker compose up -d db` + `alembic upgrade head` so the
      DB-backed events tests run) and `openspec validate --change add-events-ingest-radius-filter`
