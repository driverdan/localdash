## Why

The DB-backed tests run against the same `localdash` database the app uses, so real data leaks
into test results and tests leak writes into real data. `tests/test_news_db.py::test_stories_limit_returns_newest_slice`
fails locally right now because a real future-dated article outranks the seeded stories, and
`tests/test_api_events.py::test_refresh_endpoint_reports_counts` runs the events reconciliation pass
against real upcoming events through the app's global `SessionLocal`. Tests should own their
data: a temporary database, created for the run, holding only what the tests seed.

## What Changes

- Each pytest run that uses the database creates a uniquely named temporary database
  (`localdash_test_<run-id>`) on the configured Postgres server, migrates it to head, and drops it
  when the run completes. Databases left behind by crashed runs are swept.
- The test process's `DATABASE_URL` is pointed at the temporary database before any `app.*`
  module is imported, so the app's global engine/`SessionLocal` (used by `refresh()`, the
  scheduler, etc.) also targets it. A guard refuses to run destructive setup against any database
  whose name does not start with `localdash_test`.
- Every table except `alembic_version` is truncated between tests, so each test starts empty and
  seeds exactly the fixture data it needs.
- **BREAKING (dev workflow)**: DB-backed tests **fail** instead of skipping when Postgres is
  unreachable or migrations fail. Tests that do not request a DB fixture still run without
  Postgres.
- The `test-` prefix cleanup in `db_session`, `events_db_session`, and `news_db_session` is
  removed, along with the workarounds that exist only because of the shared database (keeping the
  real news registry in patched `SOURCES`, filtering results to "our" rows, avoiding
  `recluster()`).
- Seed data is added wherever a test currently depends on whatever the real database holds, and
  assertions weakened for the shared database are tightened to exact values (e.g.
  `reconciled >= 0`, `merged >= 1`).
- `AGENTS.md`, `CONTRIBUTING.md`, and the CI workflow comments are updated to describe the
  temporary database and fail-not-skip behavior.

Out of scope: handling future-dated news articles (the Chattanoogan pinned post). That is a
separate product bug; this change only stops it from affecting tests.

## Capabilities

### New Capabilities
- `test-isolation`: how the test suite provisions, isolates, resets, and tears down its database,
  and how DB-backed tests behave when the database is unavailable.

### Modified Capabilities
- `contributor-documentation`: the "how to run tests" scenario currently says database-backed
  tests skip unless `DATABASE_URL` points at a reachable Postgres; it must instead say they run
  against a temporary database on that server and fail if it is unreachable.

## Impact

- `tests/conftest.py`: new session-level temp-database lifecycle, `DATABASE_URL` override, safety
  guard, per-test truncation; the three DB fixtures lose their skip and prefix-cleanup paths.
- DB-backed test modules: `tests/test_news_db.py`, `tests/test_events_ingest.py`,
  `tests/test_api_events.py`, `tests/test_events_cityspark.py`, `tests/test_ingest.py`,
  `tests/test_api_timeseries.py`: shared-DB workarounds removed, seeds added, assertions tightened.
- `.github/workflows/tests.yml`: the standalone `alembic upgrade head` step and the auto-skip
  comments are no longer accurate.
- `AGENTS.md` (testing section) and `CONTRIBUTING.md` (running tests).
- No application code or runtime behavior changes. No new dependencies (uses the existing
  `psycopg` sync driver and Alembic).
- Requires the configured Postgres role to be able to `CREATE DATABASE` and create the PostGIS and
  TimescaleDB extensions. The `timescale/timescaledb-ha:pg16` superuser used locally and in CI
  can.
