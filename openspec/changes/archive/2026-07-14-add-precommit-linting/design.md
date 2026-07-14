## Context

LocalDash is a two-language repo (Python backend, Svelte/TS frontend) with no
lint or format tooling: Python has only `pytest`; the frontend has only
`svelte-check` (types, not lint). No `.git` hooks, no `core.hooksPath`, no CI.
The repo's operating philosophy is "keep works-on-my-machine out of the loop" —
runtime lives in Docker, and Node is required only to build the frontend.

Git hooks, however, fire on the **host** at commit time, outside any container.
That tension drives the tooling choice: the orchestrator should provision its
own pinned tools rather than assume a hand-configured host. These decisions were
settled during exploration (see the AskUserQuestion selections): pre-commit
framework, fix-then-abort, `ruff` + `prettier` (+ `svelte-check` still open).

## Goals / Non-Goals

**Goals:**

- One committed config that lints/formats staged Python and frontend code.
- Reproducible tool versions with minimal manual host setup.
- Fix-then-abort semantics so auto-fixes are reviewed, never silently committed.
- A clean adoption path: a baseline reformat lands separately from the hook.

**Non-Goals:**

- CI enforcement. Hooks stay bypassable via `--no-verify`; a
  `pre-commit run --all-files` CI job is a later change.
- Whole-repo linting on every commit. Scope is staged files only.
- New runtime dependencies. All added tooling is dev-only.
- Type-safety gating in the general case (see the svelte-check decision).

## Decisions

### Orchestrator: pre-commit framework

Chosen over husky+lint-staged and a bare `core.hooksPath` shell script. The
framework **pins and self-provisions** each tool (e.g. `ruff` runs from an
isolated managed environment — no global install), which fits the repo's
reproducibility ethos better than a shell script that assumes host tools. Cost:
a Python dev tool (`pre-commit`) and a one-time `pre-commit install` (hooks
never auto-install on clone).

### Python: ruff via ruff-pre-commit

`ruff check --fix` then `ruff format` — one fast tool replacing black + flake8 +
isort. Consumed through the official `ruff-pre-commit` mirror (self-provisioned),
configured in `[tool.ruff]` in `pyproject.toml` so a manual `ruff` run and the
hook share one config. Initial config stays conservative (default rule set) to
keep the baseline reformat reviewable; rule expansion is incremental.

### Frontend: prettier as a local hook

Rather than pre-commit's frozen `mirrors-prettier`, prettier runs as a **local**
hook calling the frontend's own `prettier` (added to `frontend/devDependencies`
with `prettier-plugin-svelte`). Rationale: the frontend already requires
`node_modules` for builds and `svelte-check`, so reusing it gives a single
source of version truth shared by the hook and an `npm run format` script, and
makes the Svelte plugin load naturally. `.prettierrc` holds config;
`.prettierignore` excludes `static/` (the gitignored build artifact).

### svelte-check: excluded from the hook

`svelte-check` is a **whole-project** type checker — it ignores staged-file lists
and needs `pass_filenames: false`, making it slow and scope-mismatched for a
staged-files hook. Decision: **keep it out of the pre-commit hook** and leave it
as `npm run check` (and a future CI job). This keeps the hook to fast
format+lint. Alternative considered: include it as an always-run frontend hook —
rejected for speed and because type errors, unlike formatting, are not
auto-fixable and would just block commits.

### Adoption: baseline reformat first

Nothing has ever been formatted, so the first hook run would rewrite many files.
A one-time "format the whole codebase" commit lands **before** the hook is
active, so the hook's introduction is a clean diff and subsequent commits are
near-noise-free.

## Risks / Trade-offs

- **Hooks are bypassable (`--no-verify`) and there's no CI** → accepted as an
  explicit non-goal; a CI backstop is a follow-up change. Documented so it's a
  known gap, not a surprise.
- **Host still needs `pre-commit` and `node_modules`** → mitigated by
  self-provisioning (Python side) and reuse of the already-required frontend
  toolchain; documented setup steps in `AGENTS.md`/`README.md`.
- **Large baseline-format diff** → mitigated by landing it as a standalone,
  reviewable commit separate from the hook config.
- **Ruff reformatting hand-written Alembic raw-SQL migrations** → ruff format
  only restyles Python syntax, not string contents; verify migrations still
  import/run after the baseline pass, and add an exclude if any migration is
  adversely affected.
- **Contributor forgets `pre-commit install`** → hooks silently don't run;
  mitigated by documentation and, later, CI that catches unformatted code.

## Open Questions

- None blocking. If ruff's default rules prove too noisy or too thin during the
  baseline pass, tune `[tool.ruff]` before landing — a config detail, not a
  design change.
