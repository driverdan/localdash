## ADDED Requirements

### Requirement: A change-detection job classifies each run's changed files

The CI workflow SHALL run a lightweight change-detection job before the test jobs that classifies
the files changed by the triggering event into named categories and exposes each category as a
boolean job output. The categories SHALL be:

- `python` — one or more of `app/`, `tests/`, `alembic/`, `pyproject.toml`, `uv.lock` changed
- `frontend` — one or more files under `frontend/` changed
- `docker` — `Dockerfile` or `docker-entrypoint.sh` changed

Each category's filter SHALL additionally include the workflow file itself
(`.github/workflows/tests.yml`), so that any edit to CI configuration classifies as a change in
every category and forces the full suite to run.

The detection job SHALL evaluate changes for both `pull_request` events (base branch versus head)
and `push` events (previous commit versus pushed commit).

#### Scenario: Python-only change

- **WHEN** a run's diff touches only files under `app/`
- **THEN** the detection job's `python` output is `true` and its `frontend` and `docker` outputs
  are `false`

#### Scenario: Frontend-only change

- **WHEN** a run's diff touches only files under `frontend/`
- **THEN** the detection job's `frontend` output is `true` and its `python` and `docker` outputs
  are `false`

#### Scenario: Docs-only change

- **WHEN** a run's diff touches only files under `openspec/`, `docs/`, `*.md`, or `LICENSE`
- **THEN** all of the detection job's `python`, `frontend`, and `docker` outputs are `false`

#### Scenario: Workflow edit forces full detection

- **WHEN** a run's diff modifies `.github/workflows/tests.yml`
- **THEN** the detection job's `python`, `frontend`, and `docker` outputs are all `true`

### Requirement: Test jobs run only when relevant files changed

The `pytest` job SHALL execute only when the detection job's `python` output is `true`, and the
`frontend` job SHALL execute only when the detection job's `frontend` output is `true`. A job that
is not selected SHALL be skipped rather than failed, so that it reports as a successful (skipped)
required status check and does not block merging.

Selection SHALL be implemented with job-level `if:` conditions on the detection outputs, NOT with a
workflow-level `on.*.paths` / `paths-ignore` filter, because a workflow that is filtered out never
reports its required status checks and would leave a pull request permanently blocked.

#### Scenario: Frontend-only change skips pytest

- **WHEN** a pull request changes only files under `frontend/`
- **THEN** the `pytest` job is skipped and the `frontend` job runs, and the pull request's
  required checks are all satisfied

#### Scenario: Python-only change skips frontend

- **WHEN** a pull request changes only Python-relevant files
- **THEN** the `frontend` job is skipped and the `pytest` job runs, and the pull request's
  required checks are all satisfied

#### Scenario: Docs-only change skips all test jobs

- **WHEN** a pull request changes only `openspec/` or `docs/` or Markdown files
- **THEN** the `pytest`, `frontend`, and `docker` jobs are all skipped and the pull request is
  mergeable with all required checks satisfied

#### Scenario: A skipped required job does not block the merge

- **WHEN** a required-status-check job is skipped because its category did not change
- **THEN** the skipped job reports as success for branch protection and does not hold the pull
  request in a pending state
