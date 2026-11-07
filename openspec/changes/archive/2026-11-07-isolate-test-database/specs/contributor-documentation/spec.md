## MODIFIED Requirements

### Requirement: CONTRIBUTING.md is the home for human contributor setup

The repository SHALL provide a `CONTRIBUTING.md` at the repository root that
documents everything a human contributor needs to work on the project locally:
setting up a development environment, running the test suite, and running the
linting and formatting hooks. It SHALL be written for a human reader, distinct
from `AGENTS.md`, which addresses coding agents.

#### Scenario: A contributor finds local setup instructions

- **WHEN** a human contributor opens `CONTRIBUTING.md`
- **THEN** it documents running the database in Docker and the app from a local
  virtual environment, including the dependency install, configuration, and
  migration steps
- **AND** it documents building and running the frontend dev server

#### Scenario: A contributor finds how to run tests

- **WHEN** a contributor looks for how to run the test suite
- **THEN** `CONTRIBUTING.md` documents the test command
- **AND** it explains that database-backed tests need the Postgres server named by
  `DATABASE_URL` to be running, that they run in a temporary database the test run
  creates, migrates, and drops on that server rather than in the app's database,
  and that they fail if the server is unreachable

#### Scenario: A contributor finds the linting setup

- **WHEN** a contributor looks for linting and formatting
- **THEN** `CONTRIBUTING.md` documents enabling the pre-commit hook and notes that
  it must be installed once per clone
