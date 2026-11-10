## 1. Characterization tests (on unmodified `main` code)

- [x] 1.1 In `tests/test_events_ingest.py`, add a test that a retitled re-report matched on the
  source-listing tier adopts the new `canonical_key`, and a companion test that the stored key is
  kept when another event already holds the new key (no new event, no error)
- [x] 1.2 Add a test that re-reporting the same `(source_name, source_url)` with a new
  `source_event_id` updates the existing link without adding one, and that a re-report without
  an id leaves the stored id unchanged
- [x] 1.3 Add a test that an ingest merge never overwrites a stored description, venue name,
  address or end time, and that an empty-string stored description is backfilled
- [x] 1.4 Add a test that a merge into a stored event with an address but no location, from a
  report with neither address nor coordinates, geocodes the stored address (assert
  `FakeGeocoder.calls`)
- [x] 1.5 Add a reconciliation test (dates via `upcoming()`) that the survivor gains the
  loser's missing description, venue name, address, end time, image URL and location, keeps the
  ones it already had, and ends with the union of both rows' tags (covers the new "Ingest and
  reconciliation backfill the same fields" scenario together with 1.3 and the existing image
  tests)
- [x] 1.6 Add a three-row same-day reconciliation test where the survivor matches the third row
  only through state gained from the second (inherited coordinates or adopted longer title),
  asserting one row remains with all three links
- [x] 1.7 Run `pytest tests/test_events_ingest.py` against the unmodified code and confirm the
  new tests pass. Commit them on their own, before any refactor commit

## 2. Shared helpers

- [ ] 2.1 Add `_coords(lat, lon)` and use it in `_geocode`, `_find_fuzzy_candidate` and
  `reconcile_events`
- [ ] 2.2 Add `_event_side(event, coords)` and use it for every event-side `MatchSide`
  construction (optionally `_raw_side(raw, coords)` for the one raw side)
- [ ] 2.3 Add `_backfill_missing(event, *, description, venue_name, address, ends_at,
  image_url)` and call it from both the ingest merge branch and `_merge_pair`, leaving each
  path's location handling where it is

## 3. Decompose `upsert_raw_events`

- [ ] 3.1 Extract `_find_known_event` (tier 1 + drifted-key adoption, then tier 2)
- [ ] 3.2 Extract `_locate(session, geocoder, raw, address, geo_cache)` (supplied coordinates,
  else geocode) and use it on the new-event path (`raw.address`) and the merge path
  (`event.address or raw.address`, after backfill)
- [ ] 3.3 Extract `_beyond_radius` with the same debug log, keeping the `get_settings().center`
  lookup in place
- [ ] 3.4 Extract `_tag_names(raw, blocked_tags)` (pure) and `_create_event`, keeping
  `session.add` before the first tag lookup and attaching tags in sorted order
- [ ] 3.5 Extract `_merge_report` (backfill, then location) and `_upsert_link`
- [ ] 3.6 Reduce the loop to the sequence in design.md Decision 1. Keep the per-raw `flush`,
  the single `commit`, the `blocked_tags` read once per batch, and the returned dict literal

## 4. Restructure `reconcile_events`

- [ ] 4.1 Add the `_Candidate` dataclass (`event`, `coords`, `key`) and build buckets from it
- [ ] 4.2 Extract `_reconcile_bucket`, which partitions the remaining candidates per survivor
  (no `None` tombstones, no index writes), preserving id order, survivor state updates, the
  log line and `session.delete`
- [ ] 4.3 If `_merge_pair` is still over C901 10, split out link and tag union helpers

## 5. Documentation

- [ ] 5.1 In `AGENTS.md` (events feature, `ingest.py` bullet), add one sentence: identity tiers
  are resolved by `_find_known_event` (source listing, then canonical key) and
  `_find_fuzzy_candidate`, and both merge paths share `_backfill_missing`, so a new backfilled
  field is added in one place

## 6. Verify

- [ ] 6.1 `uvx ruff check --select C901,PLR0912,PLR0915 app/events/ingest.py` reports nothing
  (ad hoc check only; `pyproject.toml` is not changed here)
- [ ] 6.2 `ruff check` and `ruff format --check` pass on changed files
- [ ] 6.3 Confirm `git diff main -- tests/` adds tests only and edits no existing test
- [ ] 6.4 Run `pytest tests/test_events_ingest.py tests/test_events_dedup.py
  tests/test_api_events.py`, then the full `pytest` suite, against the dev Postgres
- [ ] 6.5 Rebuild and run the stack (`docker compose up --build`), trigger
  `POST /api/v1/events/refresh` twice, and confirm both complete without errors in the logs
  and the second reports `reconciled: 0` (and `created` at or near 0, allowing for upstream
  changes between the calls)
- [ ] 6.6 `openspec validate decompose-events-upsert --strict`
