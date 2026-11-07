## 1. Relative dates for the reconcile tests

- [ ] 1.1 Add an `upcoming(days, hour)` helper to `tests/test_events_ingest.py` that returns an
  hour-aligned UTC datetime `days` days from now (minute, second, and microsecond zeroed)
- [ ] 1.2 In `test_reconcile_merges_preexisting_duplicates`, replace the fixed 2026-12-08 22:00
  start with `upcoming(30, 22)`
- [ ] 1.3 In `test_reconcile_merges_after_coordinates_appear`, replace the fixed 2026-12-09 22:00
  start with `upcoming(30, 22)`
- [ ] 1.4 In `test_reconcile_merges_stale_key_exact_duplicates`, replace the fixed 2026-12-10 13:00
  start with `upcoming(30, 13)`
- [ ] 1.5 Add a short comment at the top of the reconciliation section explaining that
  `reconcile_events()` only sees upcoming events, so these tests use `upcoming()` while the
  de-duplication tests keep fixed dates

## 2. Documentation

- [ ] 2.1 Add one sentence to the `AGENTS.md` testing section: tests of code that compares against
  the current time must compute dates relative to now (or inject a fixed "now"), never hard-code
  future dates

## 3. Verify

- [ ] 3.1 Confirm no December-2026 literal remains in the three reconcile tests and the
  de-duplication tests are unchanged
- [ ] 3.2 Run `pytest tests/test_events_ingest.py` against the dev Postgres and confirm all tests
  pass
- [ ] 3.3 Check the fix works past the old dates: temporarily change `upcoming()` to compute from a
  date after 2026-12-10 (or run the three reconcile tests with the system clock past it, e.g. via
  `faketime`) and confirm they still pass, then revert the temporary change
- [ ] 3.4 Run `ruff check` and `ruff format --check` on the changed test file
- [ ] 3.5 Run the full `pytest` suite
