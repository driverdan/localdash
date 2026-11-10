## Why

The Python tooling catches less than it looks like it does. Ruff runs only `E4`, `E7`, `E9`, `F`
and `I`. Eleven `# noqa: BLE001` comments (ten in `app/`, one in `tests/`) suppress a rule that is
not enabled, so they suppress nothing. There is no type checker, and many signatures are untyped or
loosely typed (`ingest(session, ...)`, `_observation(..., now, ..., geom)`, the `_entry_*(entry)`
helpers, bare `frozenset`, `list[list]`). Lint and format have no CI backstop, a gap AGENTS.md
records as deferred. The hook's pinned ruff (`v0.17.2` in `.pre-commit-config.yaml`) has already
drifted from the locked ruff (`0.17.3` in `uv.lock`), even though AGENTS.md says to keep them in
step, and Dependabot PR #324 (ruff 0.17.4) will widen the gap.

This change lands after the sibling refactors from the same architecture review. That way the
mechanical rewrite and the type fixes are done once, on the final shape of the code.

## What Changes

- Widen the ruff rule set to `E4, E7, E9, F, I, UP, B, SIM, BLE, RUF100`, with FastAPI's
  `Depends` declared as an immutable call for `B008`. Measured on the current tree: 123 hits,
  114 of them auto-fixable (107 `UP`, 6 `RUF100`, 1 `SIM905`), leaving 9 to fix by hand.
- Make the `BLE001` suppressions mean something. With `BLE` and `RUF100` on, 6 of the 10 `app/`
  suppressions turn out to be unneeded (`BLE001` already exempts handlers that call
  `log.exception`) and are removed. The other 4, plus the test one, stay as deliberate catch-alls.
  The one new hit (`app/news/fetcher.py`, the per-feed catch) gets a reasoned `noqa`. `RUF100`
  stops stale suppressions from coming back.
- Add **mypy** as a dev dependency, configured in `[tool.mypy]` in `pyproject.toml`. It checks
  `app/` with `strict = true` but leaves `disallow_any_generics` off for now, and uses the
  Pydantic plugin. It runs with `uv run mypy`. It is not a commit hook, for the same reason
  `svelte-check` is not.
- **Contributor workflow:** the ruff pre-commit hooks become `local` hooks that run
  `uv run --locked --extra dev ruff ...`, so the hook always uses the ruff version in `uv.lock`.
  The separate `rev` pin, and the AGENTS.md rule to keep it in step by hand, are removed. The hook
  now needs `uv` on `PATH`, which the documented setup already requires.
- **Contributor workflow:** close the CI gap. A new `lint` job, gated on the `python` change
  category, runs `ruff check .`, `ruff format --check .` and `mypy`. The `frontend` job gains a
  `prettier --check` step through a new `npm run format:check` script. A commit can now be blocked
  by lint errors that can't be auto-fixed (`B`, `SIM`, `BLE`), and a PR can now fail CI on lint,
  format or type errors.
- Fix the type errors mypy reports (currently 67 in 19 files: 34 missing annotations, 33 others),
  including the loose signatures above. Remove the mixed `import datetime as dt` and
  `from datetime import ...` in `app/events/ingest.py`.
- Update `alembic/script.py.mako` so newly generated migrations pass `UP` without needing an
  auto-fix.
- Update `AGENTS.md` and `CONTRIBUTING.md` (tooling, CI and linting sections).

Out of scope: the `ANN` rules (mypy owns annotation coverage), type-checking `tests/` or
`alembic/`, `disallow_any_generics`, and one `datetime` import style across all modules.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `code-quality-tooling`: the hook provisions ruff from the locked dev dependencies instead of a
  separate pre-commit pin; the rule set is specified; a type-checking requirement and a CI
  enforcement requirement are added; mypy joins the developer setup contract.
- `ci-change-filtering`: a new `lint` job is selected by the `python` category alongside `pytest`.
- `contributor-documentation`: the linting scenario also covers the type-check command and the CI
  enforcement.

## Impact

- `pyproject.toml`: `[tool.ruff.lint]` select and bugbear settings, `[tool.mypy]`, `mypy` in the
  `dev` extras; `uv.lock` re-locked.
- `.pre-commit-config.yaml`: the ruff hooks move from `astral-sh/ruff-pre-commit` to `local`.
- `.github/workflows/tests.yml`: a new `lint` job, a `prettier --check` step in `frontend`, and
  `lint` added to the `docker` job's `needs`. `frontend/package.json` gets a `format:check` script.
- About 47 Python files get the mechanical ruff rewrite (mostly `timezone.utc` to `UTC`), and about
  19 `app/` files get type fixes. All nine `alembic/versions/*` files get annotation-only rewrites.
  There is no runtime behavior change.
- `AGENTS.md` and `CONTRIBUTING.md`.
- Repository settings: `lint` must be added as a required status check, which is a manual step for
  the repo owner.
- It conflicts textually with every sibling change. See design.md, "Sequencing".
