## Why

The repo has no linters or formatters wired up for either language: Python has
only `pytest`, and the frontend has only `svelte-check` (a type checker, not a
linter). Style and lint issues are caught only by human review, if at all. A
pre-commit hook that auto-fixes and lints staged code moves that feedback to the
moment code is written, keeping the tree consistent without relying on reviewer
diligence.

## What Changes

- Adopt the **pre-commit framework** with a committed `.pre-commit-config.yaml`
  that runs on **staged files only**, with **fix-then-abort** semantics:
  hooks auto-fix, and if any file was modified the commit aborts so the
  developer reviews the changes and re-commits (pre-commit's default).
- **Python:** add `ruff` (via `ruff-pre-commit`, self-provisioned by the
  framework) running `ruff check --fix` then `ruff format`. Add a `[tool.ruff]`
  config block to `pyproject.toml`.
- **Frontend:** add `prettier` (with `prettier-plugin-svelte`) as a **local**
  hook that reuses the existing Node toolchain, plus `.prettierrc` and
  `.prettierignore` (excluding the `static/` build artifact). Add `prettier`
  and `prettier-plugin-svelte` to `frontend/devDependencies`.
- Add `pre-commit` to `pyproject.toml` `dev` optional-dependencies and add a
  `format` script to `frontend/package.json`.
- **Baseline reformat:** a one-time pass that formats the entire existing
  codebase, landed before the hook is active so its introduction is a clean,
  reviewable diff rather than a surprise on the first commit.
- **Docs:** document the one-time `pre-commit install` step (hooks do not
  auto-install on clone) in `AGENTS.md` and `README.md`.

## Capabilities

### New Capabilities

- `code-quality-tooling`: automated, pre-commit-time linting and formatting of
  staged Python and frontend code, including tool selection, hook orchestration,
  fix-then-abort behavior, and the developer setup contract.

### Modified Capabilities

<!-- None. This adds developer tooling; no product capability's requirements change. -->

## Impact

- **New files:** `.pre-commit-config.yaml`, `.prettierrc`, `.prettierignore`.
- **Modified files:** `pyproject.toml` (`[tool.ruff]` + `dev` dep),
  `frontend/package.json` (`prettier`, `prettier-plugin-svelte` devDeps +
  `format` script), `AGENTS.md`, `README.md`, and a broad baseline-format diff
  across `app/`, `tests/`, `alembic/`, and `frontend/src/`.
- **Developer workflow:** contributors must run `pre-commit install` once; the
  Python side is self-provisioned by pre-commit, the frontend side reuses
  `frontend/node_modules` (already required for builds and `svelte-check`).
- **Out of scope (known gaps):** no CI backstop is added, so hooks remain
  bypassable with `git commit --no-verify`; wiring `pre-commit run --all-files`
  into CI is deferred to a later change. Whether `svelte-check` belongs in the
  hook is settled in `design.md`.
