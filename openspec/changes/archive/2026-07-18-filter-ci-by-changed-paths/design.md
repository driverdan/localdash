## Context

`.github/workflows/tests.yml` has three jobs: `pytest`, `frontend`, and `docker` (which
`needs: [pytest, frontend]`). All three are **required status checks** on `main`. Every
`pull_request` and every push to `main` runs all of them, regardless of what changed — so an
`openspec/` or `docs/` edit pays for a full Python install + migrate + pytest, a Node install +
svelte-check + build, and a buildx image build.

The jobs have genuinely different relevance sets: `pytest` depends on `app/`, `tests/`, `alembic/`,
`pyproject.toml`, `uv.lock`; `frontend` depends on `frontend/`; `docker` builds an image containing
both, plus `Dockerfile` / `docker-entrypoint.sh`. Only `openspec/`, `docs/`, `*.md`, and `LICENSE`
are irrelevant to all three.

## Goals / Non-Goals

**Goals:**

- Skip a job when the diff cannot affect what it tests.
- Stay mergeable under required-status-check branch protection.
- Keep `docker` building whenever the image could have changed, gated on tests not failing.
- Make CI-config edits always run the full suite (no self-filtering).

**Non-Goals:**

- No change to what any job does when it runs (same steps, same image, same tags).
- No matrix expansion, no new jobs beyond the detector.
- Not attempting to skip individual test files within a job — job granularity only.

## Decisions

### Per-job `if:` gating, not workflow-level `on.*.paths`

A workflow filtered out by `on.pull_request.paths` never reports its status checks. With those
checks required, the PR sits forever on "Expected — Waiting for status to be reported." A job
skipped by a job-level `if:` instead reports as **success** to branch protection, so the PR merges.
Therefore filtering lives on the jobs, and the workflow always starts.

Alternatives considered: `on.paths-ignore` (rejected — the required-check deadlock above, and it is
all-or-nothing across jobs, so a frontend-only change could not skip only `pytest`).

### A single detection job with `dorny/paths-filter`

One cheap `changes` job (no toolchain checkout) runs `dorny/paths-filter@v3` and exposes
`python`, `frontend`, and `docker` boolean outputs. The test jobs `needs: [changes]` and gate on
those outputs. `paths-filter` handles both PR (base…head) and push (before…after) diffing and works
for fork PRs.

Alternatives considered: `tj-actions/changed-files` (heavier, larger permission surface);
hand-rolled `git diff` (re-implements edge cases paths-filter already handles).

Filter definitions (each also includes the workflow file):

```yaml
python:
  - 'app/**'
  - 'tests/**'
  - 'alembic/**'
  - 'pyproject.toml'
  - 'uv.lock'
  - '.github/workflows/tests.yml'
frontend:
  - 'frontend/**'
  - '.github/workflows/tests.yml'
docker:
  - 'Dockerfile'
  - 'docker-entrypoint.sh'
  - '.github/workflows/tests.yml'
```

### The docker job's guard

Replace `needs: [pytest, frontend]` (bare `needs` requires **both** to succeed; a skipped
dependency is not "success", so a single-sided change would wrongly skip docker) with an explicit
guard that runs when the image could have changed and no test job failed:

```yaml
docker:
  needs: [changes, pytest, frontend]
  if: >-
    ${{ !cancelled() && !failure() &&
        (needs.changes.outputs.python == 'true' ||
         needs.changes.outputs.frontend == 'true' ||
         needs.changes.outputs.docker == 'true') }}
```

- `!failure()` — if `pytest` or `frontend` failed, docker does not run (no broken image pushed).
- `!cancelled()` — a cancelled run does not sneak a build through.
- The category test — build only when the image could have changed; a docs-only run skips it.
- Because the guard tolerates a *skipped* dependency (skipped ≠ failed), a change touching only one
  side still builds. This is the "either, not both" behavior.

The existing `push`-only conditions inside the docker steps (login + `push:`) are unchanged; the
event name still gates registry access, so fork PRs stay credential-free.

### Include the workflow file in every filter

Any edit to `.github/workflows/tests.yml` sets all three categories, forcing the full suite. A CI
change must be exercised by the CI it changes; otherwise a broken workflow could filter itself out
of ever running.

## Risks / Trade-offs

- **A skipped required check must read as success** → This is standard GitHub behavior for
  job-level `if:` skips, and the branch-protection contexts (`pytest`, `frontend`, `docker`) still
  exist because the workflow always starts. Verify on the first docs-only PR that the checks turn
  green rather than pending.
- **`paths-filter` diff base on `push`** → For pushes it diffs against the event's before-commit;
  a force-push or a first commit on a branch can widen the set. Acceptable — worst case is running
  more than necessary, never less.
- **Under-building the image** → Mitigated by routing both `python` and `frontend` categories (not
  just `docker`) into the docker guard, plus `Dockerfile`/entrypoint. If the Dockerfile ever starts
  copying a path outside those categories, the filter must grow with it.
- **Requirement rename at archive** → The `docker-publish` delta keeps existing requirement headers
  to stay archive-clean; see [[openspec-archive-scenario-rename]] if a header ever must change.

## Migration Plan

Single-file edit to `.github/workflows/tests.yml`; no runtime or data migration. Rollback is
reverting that file. Validate by opening (a) a docs-only PR — expect all three jobs skipped and
green; (b) a `frontend/`-only PR — expect `pytest` skipped, `frontend` + `docker` run; (c) an
`app/`-only PR — expect `frontend` skipped, `pytest` + `docker` run.

## Open Questions

- Pin `dorny/paths-filter` to a major tag (`@v3`) consistent with the other actions here, and let
  Dependabot's `github-actions` ecosystem bump it — confirm that matches the repo's pinning
  convention for third-party (non-`astral-sh/setup-uv`) actions.
