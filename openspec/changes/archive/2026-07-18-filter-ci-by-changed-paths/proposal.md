## Why

Every push and pull request runs the full CI suite — `pytest`, `frontend`, and a Docker image
build — even when the change touches nothing those jobs exercise (an `openspec/` doc, a
`README.md`, a note in `docs/`). That spends runner minutes and wall-clock time on work whose
result is a foregone conclusion. Skipping the irrelevant jobs makes CI faster and cheaper without
weakening it.

## What Changes

- Add a lightweight `changes` detection job to `.github/workflows/tests.yml` that classifies the
  changed files (via `dorny/paths-filter`) into `python`, `frontend`, and `docker` outputs, and
  gates the existing jobs on those outputs with job-level `if:` conditions.
- `pytest` runs only when Python-relevant files changed (`app/`, `tests/`, `alembic/`,
  `pyproject.toml`, `uv.lock`). A frontend-only or docs-only change skips it.
- `frontend` runs only when `frontend/` changed. A Python-only or docs-only change skips it.
- A change confined to `openspec/`, `docs/`, `*.md`, or `LICENSE` skips all three jobs.
- The `docker` job builds when the image content could have changed — i.e. when **either**
  `pytest` **or** `frontend` ran, or when `Dockerfile` / `docker-entrypoint.sh` changed. Its
  current `needs: [pytest, frontend]` (which requires **both** to succeed) is replaced by a
  `!cancelled() && !failure() && (python || frontend || docker-files)` guard, so a single-sided
  change still builds the image while a failed or cancelled test job still blocks it.
- Every path filter also includes `.github/workflows/tests.yml`, so any edit to CI itself forces
  the full run rather than filtering itself out.

Filtering is done per-job via `if:`, **not** via a workflow-level `on.*.paths` filter. All three
jobs are required status checks on `main`; a job skipped through `if:` reports as success and lets
the PR merge, whereas a workflow skipped through `on.paths` never reports the check and leaves the
PR blocked forever.

## Capabilities

### New Capabilities

- `ci-change-filtering`: A change-detection job classifies the files touched by a run and gates
  the `pytest` and `frontend` jobs so each executes only when files it exercises changed, while
  remaining compatible with required status checks.

### Modified Capabilities

- `docker-publish`: The docker job's build trigger narrows from "every run" to "runs where image
  content could have changed", and its dependency on the test jobs changes from requiring **both**
  `pytest` and `frontend` to succeed to requiring that neither failed while at least one ran.

## Impact

- `.github/workflows/tests.yml` — new `changes` job; `if:` guards on `pytest`, `frontend`, and
  `docker`; the `docker` job's `needs`/`if:` reworked.
- New third-party action dependency: `dorny/paths-filter` (Dependabot's `github-actions`
  ecosystem already tracks actions in this repo).
- No application code, runtime, or image contents change. Behavioral change is limited to which
  CI jobs execute for a given diff.
