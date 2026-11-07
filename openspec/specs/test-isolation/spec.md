# test-isolation Specification

## Purpose

The test suite owns its data. Database-backed tests run in a temporary database
that each pytest run creates, migrates, resets between tests, and drops, on the
Postgres server named by `DATABASE_URL`. They never touch the app's database, so
real data can't change test results and tests can't change real data. This
spec covers how that database is provisioned, isolated, guarded, and torn down,
and how DB-backed tests behave when it is unavailable.

## Requirements

### Requirement: Tests use a temporary database, never the app's database

The test suite SHALL run every database-backed test against a temporary database created for that
pytest run on the Postgres server named by the configured `DATABASE_URL`. The temporary database's
name SHALL start with `localdash_test_` and SHALL be unique per run, so concurrent runs (for
example, from separate worktrees) never share one. No test SHALL read from or write to the
database named in the configured `DATABASE_URL`.

#### Scenario: A DB-backed test runs in its own database

- **WHEN** `pytest` runs a test that requests a database fixture
- **THEN** that test's session is connected to a database whose name starts with `localdash_test_`
- **AND** rows in the configured app database are neither visible to nor modified by the test

#### Scenario: Concurrent runs are isolated

- **WHEN** two `pytest` runs execute at the same time against the same Postgres server
- **THEN** each run uses a different temporary database and neither sees the other's rows

### Requirement: App code under test uses the temporary database

The temporary database's URL SHALL be in effect before any application module that builds a
database engine is imported, so application code that opens its own sessions (the global
`SessionLocal`, as used by the news and events `refresh()` paths and the scheduler) connects to the
temporary database rather than the app's database.

#### Scenario: Refresh called from a test writes to the temporary database

- **WHEN** a test calls an application function that opens a session through the global
  `SessionLocal`
- **THEN** that session is connected to the run's temporary database

### Requirement: Destructive test setup is guarded by database name

Any test-suite operation that drops, truncates, or bulk-deletes data SHALL first verify that the
target database's name starts with `localdash_test`, and SHALL abort the run with an error if it
does not.

#### Scenario: Misconfigured target is refused

- **WHEN** the test suite would truncate or drop a database whose name does not start with
  `localdash_test`
- **THEN** the run aborts with an error naming the database and no data is removed

### Requirement: The temporary database is migrated to head

Before the first database-backed test runs, the temporary database SHALL be brought to the latest
schema by running the project's Alembic migrations to head. Tests SHALL NOT depend on migrations
having been applied to the app's database.

#### Scenario: Fresh run against a server with no test database

- **WHEN** `pytest` runs a database-backed test and no temporary database exists yet
- **THEN** the temporary database is created and migrated to head before the test runs

### Requirement: Each test starts from an empty database

Before each database-backed test, every table in the temporary database except `alembic_version`
SHALL be emptied, so a test observes only the rows it seeds itself. Tests SHALL seed all data they
depend on and SHALL NOT rely on name prefixes or filtering to distinguish their rows from others.

#### Scenario: Data from a previous test is gone

- **WHEN** one test seeds rows and a later test runs in the same pytest run
- **THEN** the later test starts with every application table empty

#### Scenario: Assertions are exact

- **WHEN** a test asserts on a query result such as a count, an ordering, or a top-N slice
- **THEN** the expected value is determined entirely by the test's own seed data

### Requirement: The temporary database is removed after the run

When the pytest run completes, whether tests passed or failed, the run's temporary database SHALL
be dropped. Temporary databases left behind by runs that did not complete (for example, a killed
process) SHALL be dropped by a later run once they are old enough that they cannot belong to a run
still in progress.

#### Scenario: Clean exit removes the database

- **WHEN** a `pytest` run that created a temporary database finishes, with or without failures
- **THEN** that temporary database no longer exists on the server

#### Scenario: Stale databases from crashed runs are swept

- **WHEN** a `pytest` run starts and the server holds `localdash_test_` databases left by earlier
  runs older than the staleness threshold
- **THEN** those databases are dropped
- **AND** a `localdash_test_` database belonging to a run still in progress is not dropped

### Requirement: Database-backed tests fail rather than skip

A database-backed test SHALL fail, not skip, when the Postgres server is unreachable, when the
temporary database cannot be created, or when migrations fail. Tests that do not request a database
fixture SHALL run without a Postgres server.

#### Scenario: Postgres is down

- **WHEN** `pytest` runs and the configured Postgres server is unreachable
- **THEN** every database-backed test is reported as an error or failure, not as skipped
- **AND** tests that do not use a database fixture still run and pass

#### Scenario: Migration failure

- **WHEN** migrating the temporary database to head fails
- **THEN** the database-backed tests fail with the migration error

