## Context

Today the three DB fixtures in `tests/conftest.py` (`db_session`, `events_db_session`,
`news_db_session`) each build an async engine from `get_settings().database_url`, which is the same
`localdash` database the running app uses. Each fixture skips when the database is unreachable and
cleans up only rows matching a naming convention (`source_key == "test"`, `test-%` news slugs,
`test-%` event source names and geocode addresses).

Problems with the shared database, all seen in the current tree:

- **Real data changes test results.** `test_stories_limit_returns_newest_slice` fails locally
  because a real Chattanoogan article dated 2026-11-28 sits at #1, pushing a seeded story out of
  the `limit=5` slice. Several tests have been weakened to tolerate real rows: `reconciled >= 0`
  (`test_api_events.py:160`), `merged >= 1  # shared DB may hold other genuine duplicates`
  (`test_events_ingest.py:765`), "ours" filtering in `test_news_db.py`, `_events()` filtering by
  `test-%` in `test_events_ingest.py`.
- **Tests write to real data.** `app/db.py` builds a global `engine`/`SessionLocal` at import
  time. `test_refresh_endpoint_reports_counts` calls the events `refresh()`, which opens a session
  through that global and runs the reconciliation pass over real upcoming events.
- **Workarounds protect real data.** `test_news_db.py` keeps the real news registry in patched
  `SOURCES` so a test sync doesn't delete real outlets, and avoids `recluster()` because it "would
  rewrite real rows in a shared dev DB".
- **Concurrent runs collide.** Agent worktrees under `.claude/worktrees/` run pytest against the
  same database and the same `test-*` rows.

Constraints:

- Migrations need PostGIS and TimescaleDB (`0001_initial.py` runs `CREATE EXTENSION postgis` and
  `create_hypertable('observations', ...)`). Both are in the `timescale/timescaledb-ha:pg16` image
  used by `docker-compose.yml` and by the CI service container. Its `POSTGRES_USER` is a superuser.
- The developer runs Docker via `sg docker`, so tests cannot assume they can start containers
  themselves.
- pytest-asyncio runs in `auto` mode with function-scoped event loops.
- `alembic/env.py` calls `logging.config.fileConfig(...)`, which disables existing loggers by
  default. Three test modules use `caplog`.

## Goals / Non-Goals

**Goals:**

- No test reads or writes the app's database.
- Every DB-backed test starts from an empty, fully migrated schema and asserts exact values against
  its own seed data.
- App code that opens its own sessions (`refresh()`, scheduler) is isolated too, without
  per-test monkeypatching.
- DB-backed tests fail loudly when Postgres is unavailable. Pure tests still run without Postgres.
- Concurrent runs on one server do not interfere. Nothing accumulates on the server.

**Non-Goals:**

- Fixing future-dated news articles (handled separately by the user).
- Speeding up the suite (template databases, parallel xdist workers). The per-run migration cost
  is accepted.
- Starting Postgres for the developer. The server named by `DATABASE_URL` must already be running.
- Changing application code or runtime behavior.

## Decisions

### 1. A temporary database on the configured server

The test run creates `localdash_test_<epoch>_<rand>` on the server from the configured
`DATABASE_URL`, using a sync psycopg connection to the `postgres` maintenance database in
autocommit mode (`CREATE DATABASE` / `DROP DATABASE` cannot run in a transaction).

*Alternatives considered:*

- **Testcontainers.** Needs Docker socket access, which the developer's user doesn't have, and
  would start the large timescaledb-ha image on every run.
- **pytest-postgresql or a local `pg_ctl` instance.** Needs local Postgres binaries plus PostGIS
  and TimescaleDB builds.
- **Keep the shared database and improve prefix hygiene.** Doesn't fix global-`SessionLocal`
  writes or real rows affecting results.

The name includes the creation epoch so stale databases can be recognized by age (decision 6) and
a random suffix so concurrent runs never collide.

### 2. Override `DATABASE_URL` at the top of `conftest.py`, before any `app.*` import

`tests/conftest.py` reads the configured URL once (`Settings()`, which reads the environment and
`.env`), derives the test URL by replacing only the database name (`sqlalchemy.engine.make_url(...)
.set(database=...)`), writes it to `os.environ["DATABASE_URL"]`, and calls
`get_settings.cache_clear()`. pytest imports `conftest.py` before collecting test modules, and
pydantic-settings gives environment variables precedence over `.env`. So `app/db.py`'s import-time
engine, every `get_settings()` call, and tests that build `Settings(_env_file=None, ...)` all
resolve to the temporary database.

*Alternative:* monkeypatching `SessionLocal` per module in each test. That's opt-in, easy to
forget, and exactly how `test_refresh_endpoint_reports_counts` slipped through.

The configured URL is kept separately (only the server, user and password are reused) for the
maintenance connection. Only `conftest.py`'s top-level code may import `app.config` before the
override. Nothing above it may import `app.db` or anything that imports it.

### 3. Created lazily by a session-scoped sync fixture, so pure tests don't need Postgres

A session-scoped, non-autouse fixture (`test_database`) creates and migrates the database the first
time a DB fixture requests it, and registers its teardown. The three DB fixtures depend on it.
Pure tests never request it, so `pytest tests/test_news_clustering.py` works with Postgres down.
The fixture is sync (psycopg plus a subprocess), so it doesn't need a session-scoped event loop.

If creation or migration raises, pytest caches the session fixture's error and reports every
dependent test as an error. There is no `pytest.skip` anywhere in the DB path. This implements
"fail, not skip".

### 4. Migrate with Alembic in a subprocess

`subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], env=<with test URL>,
check=True)`, capturing output so a failure shows Alembic's error.

*Alternative:* in-process `alembic.command.upgrade`. `env.py`'s `fileConfig` would disable the
loggers that `caplog`-based tests rely on, and it would also interact with the `get_settings`
cache. A subprocess costs about a second and has no side effects.

This also makes CI's separate "Migrate" step (which migrates the `localdash` database that no
test uses anymore) redundant. It is removed. Migrating a fresh database to head is still exercised
on every CI run, by the fixture.

### 5. Reset by truncating before each test

Each DB fixture, before yielding, runs one statement:
`TRUNCATE <all public tables> RESTART IDENTITY CASCADE`. The table list comes from `pg_tables`
where `schemaname = 'public'`, minus `alembic_version` and PostGIS's `spatial_ref_sys`. It is
computed once per run and cached. TimescaleDB supports `TRUNCATE` on hypertables, and its
internal chunk tables live outside `public`.

The reset runs through a shared sync helper on its own psycopg connection, so it doesn't depend on
the test's event loop, and it checks the target name with the guard (decision 7).

*Alternatives considered:*

- **Wrap each test in a transaction or savepoint and roll back.** Code under test opens its own
  sessions through `SessionLocal` (the `refresh()` paths). Those sessions wouldn't see the test's
  uncommitted seeds, and their own commits wouldn't be rolled back.
- **Create a fresh database per test.** Migrating about 280 times is far too slow.
- **Truncate after each test instead of before.** Truncating before also handles a previous test
  that crashed mid-teardown, and it's equally cheap.

Truncating from `pg_tables` rather than `Base.metadata` also catches any table that only a
migration creates.

### 6. Teardown and sweeping stale databases

The `test_database` fixture's finalizer runs `DROP DATABASE <name> WITH (FORCE)` at session end,
whether tests passed or failed. `WITH (FORCE)` (PG ≥ 13) ends any remaining connections: pooled
connections from the global engine, and TimescaleDB background workers, which connect to
databases that have the extension and would otherwise block the drop.

Before creating its own database, the run sweeps `localdash_test_*` databases whose embedded
epoch is more than **1 hour** old, also with `WITH (FORCE)`. A full suite takes minutes, so an
hour-old database cannot belong to a live run, and dropping by age avoids killing a concurrent
run's database. `kill -9` and similar crashes are cleaned up by the next run.

*Alternative:* sweep any test database with no active connections. That would race with a
concurrent run between `CREATE DATABASE` and its first connection.

### 7. Safety guard

A single helper, `_assert_test_database(name)`, raises (aborting the run) unless the name starts
with `localdash_test`. The truncate, drop and sweep code paths all go through it, so a mistake in
deriving the URL can never truncate or drop the app's database.

### 8. Global engine and per-test event loops

`app.db.engine` is created once per process, but each test gets its own event loop, and asyncpg
connections are tied to the loop that created them. The DB fixtures' teardown therefore runs
`await app.db.engine.dispose()` in the test's own loop, so a pooled connection is never reused on
a later test's loop. This matters more after this change, because the global engine is now
expected to be used by tests.

### 9. Test rewrites: delete workarounds, add seeds, tighten assertions

Seed helpers stay as they are. Prefixed names (`test-...`) may stay, but no test relies on them for
isolation. For each DB-backed module:

- **`test_news_db.py`:**
  - drop the `_REAL_SOURCES` merge (patch `SOURCES` with test sources only);
  - compare the full `payload["stories"]` list instead of filtering to "ours";
  - remove the "would rewrite real rows" caveat.
- **`test_events_ingest.py`:**
  - `_events()` returns all events;
  - `merged >= 1` becomes `merged == 1`.
- **`test_api_events.py`:**
  - seed a known upcoming duplicate pair and assert `reconciled` equals the expected count;
  - check tag listings exactly against seeded tags.
- **`test_ingest.py`, `test_api_timeseries.py`, `test_events_cityspark.py`:** audit for
  any filtering or `>=`/subset assertions that only exist because of shared rows, and make them
  exact.

## Risks / Trade-offs

- **[Risk] A contributor's Postgres role can't `CREATE DATABASE` or create extensions** →
  The fixture fails with the server's error and a message pointing at the requirement (documented
  in `CONTRIBUTING.md`/`AGENTS.md`). Both compose and CI use a superuser.
- **[Risk] Something imports `app.db` before the override** (for example, a future import added at
  the top of `conftest.py`) → The global engine would point at the app's database. Mitigations:
  - the override code sits first in `conftest.py` with a comment explaining why;
  - the `test_database` fixture asserts that `app.db.engine.url.database` equals the temporary
    name before any test runs, and fails the run if not.
- **[Trade-off] Developers who used to run the full suite without Postgres now see DB tests
  error** → This is what the user asked for. Pure tests remain runnable in isolation.
- **[Trade-off] Migrations run on every run (a few seconds)** → Accepted. A cached template
  database keyed by Alembic head is a possible later optimization.
- **[Risk] Ctrl-C during teardown leaves a database behind** → The next run's age-based sweep
  drops it.
- **[Risk] Hidden reliance on the previous run's or the dev database's rows** (for example, a test
  that passed only because real news sources existed) → These show up as failures once the
  database is empty. Fix each by seeding, never by pointing back at shared data.

## Migration Plan

This affects tests and docs only. Local developers need `docker compose up -d db` running, as
before. They no longer need to run `alembic upgrade head` on their app database to run tests.
Rollback is reverting the PR. No data or schema changes.
