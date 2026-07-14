# code-quality-tooling Specification

## Purpose

The repository's code-quality tooling: a committed `.pre-commit-config.yaml` that runs linting and
formatting on staged files via the pre-commit framework. Python is linted and formatted with `ruff`
(provisioned by pre-commit, configured via `[tool.ruff]` in `pyproject.toml`), and frontend files
are formatted with `prettier` + `prettier-plugin-svelte` (reusing the repository's Node toolchain).
Hooks follow a fix-then-abort model — auto-modifications abort the commit for review rather than
silently re-staging — and the setup is a single `pre-commit install` documented for contributors.

## Requirements

### Requirement: Pre-commit hook orchestration

The repository SHALL provide a committed `.pre-commit-config.yaml` that runs
linting and formatting hooks via the pre-commit framework. Hooks SHALL operate
on **staged files only** and SHALL be installable with a single
`pre-commit install` command.

#### Scenario: Hooks run on commit

- **WHEN** a developer runs `git commit` after `pre-commit install`
- **THEN** the configured hooks execute against the staged files before the
  commit is recorded

#### Scenario: Only staged files are processed

- **WHEN** the working tree contains unstaged changes alongside staged changes
- **THEN** the hooks process only the staged content, leaving unstaged changes
  untouched

### Requirement: Fix-then-abort behavior

When a hook auto-modifies a staged file, the commit SHALL abort so the developer
can review the applied changes and re-commit. Hooks SHALL NOT silently re-stage
and commit modified content.

#### Scenario: Auto-fix aborts the commit

- **WHEN** a formatter or auto-fixer rewrites a staged file during the hook run
- **THEN** the commit fails, the modified files are left in the working tree for
  review, and the developer must re-stage and re-commit

#### Scenario: Clean code commits without interruption

- **WHEN** all staged files already satisfy the configured lint and format rules
- **THEN** the hooks pass and the commit completes without modification

### Requirement: Python linting and formatting

The hook configuration SHALL lint and format staged Python files with `ruff`,
running `ruff check --fix` followed by `ruff format`. Ruff SHALL be provisioned
by the pre-commit framework (no global host install required) and configured via
a `[tool.ruff]` block in `pyproject.toml`.

#### Scenario: Python file is linted and formatted

- **WHEN** a developer stages a `.py` file with a fixable lint issue or
  non-canonical formatting
- **THEN** `ruff check --fix` and `ruff format` apply the fixes and the commit
  aborts for review per the fix-then-abort behavior

### Requirement: Frontend formatting

The hook configuration SHALL format staged frontend files (`.ts`, `.svelte`,
`.css`, `.json`) with `prettier` using `prettier-plugin-svelte`, invoked as a
local hook that reuses the repository's Node toolchain. Prettier SHALL ignore
the `static/` build-artifact directory.

#### Scenario: Svelte component is formatted

- **WHEN** a developer stages a `.svelte` file with non-canonical formatting
- **THEN** prettier reformats it and the commit aborts for review per the
  fix-then-abort behavior

#### Scenario: Build artifacts are excluded

- **WHEN** files under `static/` are present
- **THEN** prettier does not reformat them

### Requirement: Developer setup contract

The repository documentation (`AGENTS.md` and `README.md`) SHALL instruct
contributors to run `pre-commit install` once, and SHALL declare the tooling as
development dependencies: `pre-commit` in `pyproject.toml` `dev` extras, and
`prettier` plus `prettier-plugin-svelte` in `frontend/devDependencies`.

#### Scenario: New contributor enables hooks

- **WHEN** a contributor follows the documented setup steps
- **THEN** they install the dev dependencies and run `pre-commit install`, after
  which hooks fire on subsequent commits
