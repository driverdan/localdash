## 1. Temporary database lifecycle (`tests/conftest.py`)

- [x] 1.1 At the very top of `conftest.py`, before any `app.*` import other than `app.config`: read the configured URL via `Settings()`, generate `localdash_test_<epoch>_<rand>`, derive the test URL with `make_url(...).set(database=...)`, set `os.environ["DATABASE_URL"]`, call `get_settings.cache_clear()`, and keep the original URL for maintenance connections. Add a comment explaining why this must come first
- [x] 1.2 Add `_assert_test_database(name)`, which raises unless the name starts with `localdash_test`
- [x] 1.3 Add a maintenance helper that opens a sync psycopg autocommit connection to the server's `postgres` database (using the original URL's host, port, user and password)
- [x] 1.4 Add a stale-database sweep: list `localdash_test_%` databases, parse the embedded epoch, and `DROP DATABASE ... WITH (FORCE)` those older than 1 hour (each through the guard)
- [x] 1.5 Add the session-scoped, non-autouse sync fixture `test_database`. It sweeps, runs `CREATE DATABASE`, runs `python -m alembic upgrade head` in a subprocess with the test URL in its environment (`check=True`, output captured and shown on failure), and asserts `app.db.engine.url.database` equals the temporary name. Its finalizer runs `DROP DATABASE ... WITH (FORCE)` through the guard
- [x] 1.6 Add a sync reset helper that guards the name, computes once the list of `public` tables from `pg_tables` (excluding `alembic_version` and `spatial_ref_sys`), and runs one `TRUNCATE ... RESTART IDENTITY CASCADE`

## 2. DB fixtures

- [x] 2.1 Rewrite `db_session`, `events_db_session` and `news_db_session` to depend on `test_database`, call the reset helper before yielding, and connect with `get_settings().database_url`
- [x] 2.2 Remove every `pytest.skip` path and every `test`-prefix delete from the three fixtures, so connection, creation and migration errors surface as test errors
- [x] 2.3 In each fixture's teardown, `await app.db.engine.dispose()` (in the test's own loop) and dispose the fixture's own engine
- [x] 2.4 Update the fixtures' docstrings to describe the temporary database and per-test reset

## 3. Test rewrites: seeds and exact assertions

- [x] 3.1 `tests/test_news_db.py`:
  - patch `registry.SOURCES` with test sources only (drop `_REAL_SOURCES`);
  - assert full story lists exactly in the limit/omitted-limit tests (no "ours" filtering);
  - assert sources and stories without `next(...)` filtering where the result is now fully determined;
  - remove the shared-DB comments
- [x] 3.2 `tests/test_events_ingest.py`:
  - `_events()` returns all events (no `test-%` filter);
  - `merged >= 1` becomes `merged == 1`;
  - update the module docstring
- [x] 3.3 `tests/test_api_events.py`:
  - in `test_refresh_endpoint_reports_counts`, seed a known upcoming duplicate pair and assert `reconciled` equals the expected count;
  - assert the tags endpoint result exactly against the seeded tags;
  - remove the shared-DB comments and update the module docstring
- [x] 3.4 Audit `tests/test_ingest.py`, `tests/test_api_timeseries.py` and `tests/test_events_cityspark.py` for filtering or `>=`/subset assertions that exist only because of shared rows. Make them exact and add any seed data they were silently getting from the real database
- [x] 3.5 Grep `tests/` for remaining shared-DB wording ("shared", "real rows", "real DB", "skips if") and remove or rewrite it

## 4. CI and docs

- [x] 4.1 `.github/workflows/tests.yml`: remove the standalone `alembic upgrade head` step, and rewrite the service-container and env comments (DB tests fail rather than skip; the suite creates, migrates and drops its own temporary database on the service)
- [x] 4.2 `AGENTS.md` testing section: replace the auto-skip and "share data with your running app" text with the temporary-database lifecycle, fail-not-skip behavior, the `localdash_test` guard, and the `CREATE DATABASE`/extension privilege requirement
- [x] 4.3 `CONTRIBUTING.md` Tests section: Postgres must be running (`docker compose up -d db`), no `alembic upgrade head` is needed for tests, tests run in a temporary database that is dropped afterwards, and DB tests fail if the server is unreachable

## 5. Verification

- [x] 5.1 With the compose DB up, the full `pytest` run passes, including `tests/test_news_db.py::test_stories_limit_returns_newest_slice`, and no test is skipped for DB reasons
- [x] 5.2 Row counts in the app's `localdash` database (news, events, entities, observations) are unchanged by a full run, and no `localdash_test_*` database remains afterwards
- [x] 5.3 With the DB stopped, DB-backed tests are reported as errors (not skips), and `pytest tests/test_news_clustering.py` still passes
- [x] 5.4 Two concurrent `pytest` runs both pass, and each uses its own temporary database
- [x] 5.5 A run killed with `kill -9` leaves a database behind that a later run drops once it is over an hour old (simulate by creating `localdash_test_<old-epoch>_x` by hand)
- [x] 5.6 `ruff` and the pre-commit hooks pass on the changed files
