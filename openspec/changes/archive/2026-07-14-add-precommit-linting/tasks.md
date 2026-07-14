## 1. Tool configuration

- [x] 1.1 Add a `[tool.ruff]` block to `pyproject.toml` (target Python 3.11+, conservative default rule set) and add `pre-commit` to the `dev` optional-dependencies.
- [x] 1.2 Add `prettier` and `prettier-plugin-svelte` to `frontend/devDependencies` and a `format` script to `frontend/package.json`; run `npm install` to update the lockfile.
- [x] 1.3 Create `.prettierrc` (enabling `prettier-plugin-svelte`) and `.prettierignore` (excluding `static/` and other build/vendored output).

## 2. Baseline reformat (separate commit)

- [x] 2.1 Run `ruff check --fix` and `ruff format` across `app/`, `tests/`, and `alembic/`; confirm the test suite and Alembic migrations still import/run.
- [x] 2.2 Run prettier across `frontend/src/` (`.ts`, `.svelte`, `.css`, `.json`); confirm `npm run build` and `npm run check` still pass.
- [x] 2.3 Commit the baseline reformat as a standalone commit, before the hook config lands.

## 3. Pre-commit hook

- [x] 3.1 Create `.pre-commit-config.yaml`: `ruff-pre-commit` hooks (`ruff check --fix`, then `ruff format`) for Python, and a local prettier hook (reusing the frontend toolchain) for `.ts`/`.svelte`/`.css`/`.json`.
- [x] 3.2 Confirm `svelte-check` is intentionally excluded from the hook (kept as `npm run check`).
- [x] 3.3 Run `pre-commit install`, then `pre-commit run --all-files` to verify hooks pass on the now-formatted tree.

## 4. Verification

- [x] 4.1 Stage a deliberately mis-formatted `.py` file and a `.svelte` file; verify the commit aborts with files auto-fixed (fix-then-abort), and succeeds after re-staging.
- [x] 4.2 Verify hooks act on staged content only (unstaged changes untouched) and that `static/` is not reformatted.

## 5. Documentation

- [x] 5.1 Document the one-time `pre-commit install` step and the dev-dependency setup in `AGENTS.md` and `README.md`.
- [x] 5.2 Note the known gap in `AGENTS.md`: hooks are bypassable via `--no-verify` and no CI backstop exists yet (deferred to a later change).
