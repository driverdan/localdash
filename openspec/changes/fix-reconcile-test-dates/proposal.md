## Why

Three reconciliation tests in `tests/test_events_ingest.py` seed events on fixed dates (December 8,
9, and 10, 2026). `reconcile_events()` only considers events with `starts_at >= now()`, so once
those dates pass the seeded events drop out of the pass and the tests fail. That starts happening
in about a month (2026-12-08) with no code change. The seeded dates should be computed from the
current time so the tests stay valid.

## What Changes

- Add a small test helper in `tests/test_events_ingest.py` that returns an hour-aligned UTC
  datetime a given number of days in the future.
- Use it for the seeded start times in the three reconcile tests:
  `test_reconcile_merges_preexisting_duplicates`, `test_reconcile_merges_after_coordinates_appear`,
  and `test_reconcile_merges_stale_key_exact_duplicates`.
- Leave the other December-dated tests in the file (the tiered de-duplication tests, December 3–6
  and 12) on fixed dates. They go through `upsert_raw_events()`, which has no "upcoming only"
  filter; the July–September dates in the same file are already past and those tests still pass.
  A short comment explains why only the reconcile tests use relative dates.
- Add a test-isolation requirement that tests must not depend on the date they run, and one
  sentence in the `AGENTS.md` testing section saying so, so the same problem isn't reintroduced.

Out of scope: any change to `reconcile_events()` or other application code.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `test-isolation`: adds a requirement that tests don't start failing as the calendar advances.
  Tests that exercise "now"-relative behavior must derive their dates from the current time or
  inject a fixed "now".

## Impact

- `tests/test_events_ingest.py`: one new helper, a short comment, and three changed `start = ...`
  lines.
- `AGENTS.md`: one sentence in the testing section.
- No application code, dependency, or runtime behavior changes.
