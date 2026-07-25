# contributor-documentation Specification

## Purpose

`CONTRIBUTING.md` is the entry point for a human contributing to LocalDash. It
owns the practical mechanics of working on the project — setting up a local
development environment, running the tests, and running the linting and
formatting tools — so that this material has exactly one home and does not
drift between copies. It is deliberately distinct from `AGENTS.md`, which
addresses coding agents and owns architecture and workflow, and from
`README.md`, which orients newcomers and links here.

## Requirements

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
- **AND** it explains that database-backed tests skip unless `DATABASE_URL` points
  at a reachable Postgres

#### Scenario: A contributor finds the linting setup

- **WHEN** a contributor looks for linting and formatting
- **THEN** `CONTRIBUTING.md` documents enabling the pre-commit hook and notes that
  it must be installed once per clone

### Requirement: CONTRIBUTING.md links to agent guidance rather than restating it

`CONTRIBUTING.md` SHALL link to `AGENTS.md` for architecture and for the git and
OpenSpec workflow rather than duplicating that content, so that each piece of
guidance has exactly one home.

#### Scenario: Architecture is linked, not copied

- **WHEN** a contributor looks for how the app is structured internally
- **THEN** `CONTRIBUTING.md` links to `AGENTS.md`
- **AND** it does not restate the data model or the collector pipeline

#### Scenario: Git workflow is linked, not copied

- **WHEN** a contributor looks for branch naming, the pull request process, or the
  OpenSpec three-PR lifecycle
- **THEN** `CONTRIBUTING.md` links to `AGENTS.md`

### Requirement: CONTRIBUTING.md stays accurate

When a change alters the development environment, the test commands, or the
linting and formatting tooling, `CONTRIBUTING.md` SHALL be updated in the same
change.

#### Scenario: Tooling change updates the doc

- **WHEN** a change alters how dependencies are installed, how tests are run, or
  which linters run on commit
- **THEN** `CONTRIBUTING.md` is updated in that same change

#### Scenario: Documented commands exist

- **WHEN** a reader runs a command documented in `CONTRIBUTING.md`
- **THEN** that command is defined by the repository's current tooling
  configuration
