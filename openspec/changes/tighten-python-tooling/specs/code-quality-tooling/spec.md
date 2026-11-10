## MODIFIED Requirements

### Requirement: Python linting and formatting

The hook configuration SHALL lint and format staged Python files with `ruff`,
running `ruff check --fix` followed by `ruff format`. Ruff SHALL be configured via
a `[tool.ruff]` block in `pyproject.toml`. The hooks SHALL run ruff from the
project's locked development dependencies (as `local` hooks invoking
`uv run --locked --extra dev ruff ...`), so that the hook, a manual `uv run ruff`,
and CI all use the single ruff version recorded in `uv.lock`. The hook
configuration SHALL NOT pin a separate ruff version.

#### Scenario: Python file is linted and formatted

- **WHEN** a developer stages a `.py` file with a fixable lint issue or
  non-canonical formatting
- **THEN** `ruff check --fix` and `ruff format` apply the fixes and the commit
  aborts for review per the fix-then-abort behavior

#### Scenario: Hook uses the locked ruff version

- **WHEN** `uv.lock` records a given ruff version and the hook runs
- **THEN** the hook executes that same ruff version, with no second version pin in
  `.pre-commit-config.yaml` to keep in step

#### Scenario: Unfixable lint error blocks the commit

- **WHEN** a developer stages a `.py` file with a lint error that ruff cannot
  auto-fix (for example a blind `except Exception` without a reasoned `noqa`)
- **THEN** the commit fails and reports the error until the developer fixes it

### Requirement: Developer setup contract

The repository documentation (`AGENTS.md` and `CONTRIBUTING.md`) SHALL instruct
contributors to run `pre-commit install` once, and SHALL declare the tooling as
development dependencies: `pre-commit`, `ruff`, and `mypy` in `pyproject.toml`
`dev` extras, and `prettier` plus `prettier-plugin-svelte` in
`frontend/devDependencies`. The documentation SHALL state that the Python hooks
require `uv` on `PATH`.

#### Scenario: New contributor enables hooks

- **WHEN** a contributor follows the documented setup steps
- **THEN** they install the dev dependencies and run `pre-commit install`, after
  which hooks fire on subsequent commits

#### Scenario: Setup instructions are reachable from the README

- **WHEN** a contributor starts from `README.md`
- **THEN** it links to `CONTRIBUTING.md`, where the `pre-commit install` step is
  documented

#### Scenario: Type checker is installed with the dev extras

- **WHEN** a contributor runs `uv sync --extra dev`
- **THEN** `uv run mypy` is available at the version recorded in `uv.lock`

## ADDED Requirements

### Requirement: Python lint rule set

The `[tool.ruff.lint]` configuration SHALL select at least the rule families
`E4`, `E7`, `E9`, `F`, `I`, `UP`, `B`, `SIM`, `BLE`, and the rule `RUF100`.
FastAPI's `Depends` SHALL be declared an immutable call for the bugbear
function-call-in-default-argument rule rather than suppressed per line. Every
`# noqa` comment SHALL name a rule that is enabled and that would otherwise fire on
that line; `RUF100` enforces this. A suppression of a deliberate broad exception
handler SHALL carry a short reason.

#### Scenario: Stale suppression is reported

- **WHEN** a file contains a `# noqa` naming a rule that is not enabled, or one
  that does not fire on that line
- **THEN** `ruff check` reports it as `RUF100` and `ruff check --fix` removes it

#### Scenario: New blind exception handler is flagged

- **WHEN** code adds `except Exception:` that neither re-raises nor logs the
  exception with `log.exception`
- **THEN** `ruff check` reports `BLE001` unless the line carries a reasoned
  `# noqa: BLE001`

#### Scenario: FastAPI dependency defaults are not flagged

- **WHEN** a route declares a parameter with a `Depends(...)` default
- **THEN** `ruff check` reports no `B008` for it

### Requirement: Python type checking

The repository SHALL type-check the `app/` package with `mypy`, configured in a
`[tool.mypy]` block in `pyproject.toml` with `strict` enabled (any relaxation of an
individual strict flag SHALL be stated in the config with a reason) and the Pydantic
mypy plugin. Third-party modules without type information SHALL be listed in
per-module overrides rather than ignored globally. `uv run mypy` with no arguments
SHALL check the configured files and SHALL report zero errors on `main`. The type
checker SHALL NOT run in the pre-commit hook.

#### Scenario: Type check passes on main

- **WHEN** a contributor runs `uv run mypy` on a clean checkout of `main`
- **THEN** it checks `app/` and reports no errors

#### Scenario: Unannotated function is rejected

- **WHEN** a change adds a function in `app/` without parameter or return
  annotations
- **THEN** `uv run mypy` reports an error for it

#### Scenario: Type checker is not a commit hook

- **WHEN** a developer commits staged Python files
- **THEN** mypy does not run as part of the hook

### Requirement: CI enforcement of lint, format, and types

CI SHALL fail a pull request whose tree violates the configured lint, format, or
type rules, independently of whether the contributor's commit hook ran. A `lint`
job SHALL run `ruff check .`, `ruff format --check .`, and `mypy` from the locked
dev dependencies, and the `frontend` job SHALL run `prettier --check` over
`frontend/`. These checks SHALL run in check mode and SHALL NOT modify files.

#### Scenario: Hook bypassed, CI catches it

- **WHEN** a pull request contains a Python lint, format, or type error committed
  with `git commit --no-verify`
- **THEN** the `lint` job fails

#### Scenario: Unformatted frontend file fails CI

- **WHEN** a pull request contains a frontend file that prettier would reformat
- **THEN** the `frontend` job fails

#### Scenario: Ruff upgrade surfaces new findings on its own PR

- **WHEN** a dependency PR bumps ruff or mypy in `uv.lock` and the new version
  reports findings on the existing tree
- **THEN** the `lint` job fails on that PR rather than on a later unrelated one
