## Why

`upsert_raw_events` in `app/events/ingest.py` (lines 161-286) does everything in one loop body:
tiered identity resolution (source listing, drifted-key adoption, canonical key, fuzzy match),
geocoding, the radius filter, event creation, tagging with the blocklist, merge backfill, and the
link upsert. Ruff reports cyclomatic complexity 22 (C901), 23 branches (PLR0912) and 63
statements (PLR0915). The merge backfill (lines 244-253) repeats the same five-field rule as
`_merge_pair` (lines 293-302, itself C901 at 12), so a field added to one path can be missed in
the other. `MatchSide` is built by hand four times, and `reconcile_events` tracks its state in
positional `[event, coords, key]` lists that it mutates by index and tombstones with `None`.
The de-duplication tiers have the most edge cases of any events code, and this structure makes
them hard to read and easy to break.

## What Changes

- Split the `upsert_raw_events` loop body into private helpers in `app/events/ingest.py`: one
  for tiers 1-2 (source listing with drifted-key adoption, then exact canonical key), one that
  locates a raw report (supplied coordinates, else geocode), one for the radius check, one that
  creates and tags a new event, one that merges a report into an existing event, and one that
  upserts the listing's link. The loop becomes a short sequence of calls.
- Add one `_backfill_missing` helper for the five shared fields (description, venue name,
  address, end time, image URL). Both the ingest merge path and `_merge_pair` call it. Location
  handling stays specific to each path: ingest geocodes, reconciliation copies the loser's point.
- Add an `_event_side(event, coords)` builder for `MatchSide` and a `_coords(lat, lon)` helper
  for the nullable-latitude tuple.
- Replace `reconcile_events`' positional lists with a small `_Candidate` dataclass, and replace
  the `None` tombstones by partitioning each day bucket so merged rows are dropped from the
  remaining work.
- Add characterization tests, before any code moves, for edge cases the current suite does not
  pin down (see design.md).
- No behaviour change: the tiers, their order, the stats dict, log lines, and every documented
  edge case stay as they are. The `events` delta spec only clarifies wording: it states that
  ingest merges and reconciliation backfill the same field set, which the code already does.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `events`: the "Cross-source de-duplication on ingest" requirement now names one backfill field
  set (description, venue name, address, end time, image URL) shared by ingest merges and
  reconciliation merges, plus each path's location rule. The current text lists the fields
  differently in its two places and leaves the image to a separate requirement. This is a
  wording fix with no change in behaviour.

## Impact

- `app/events/ingest.py`: internal restructuring only. Public functions (`upsert_raw_events`,
  `reconcile_events`, `run_sources`, `retry_failed_geocodes`, `purge_blocked_tags`) keep their
  signatures and return values. `_point` and `_as_utc` stay where they are (tests import
  `_point`).
- `tests/test_events_ingest.py`: new characterization tests; existing tests unchanged.
- `AGENTS.md`: the events `ingest.py` bullet gains a sentence on where the tiers and the shared
  backfill rule live.
- No API, schema, migration, config, or dependency changes.
- Overlaps with sibling changes that edit the same file: `inject-settings-and-clock` and
  `consolidate-shared-helpers` should land after this one (see design.md).
