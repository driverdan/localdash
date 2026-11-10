## MODIFIED Requirements

### Requirement: Test jobs run only when relevant files changed

The `pytest` and `lint` jobs SHALL execute only when the detection job's `python` output is
`true`, and the `frontend` job SHALL execute only when the detection job's `frontend` output is
`true`. A job that is not selected SHALL be skipped rather than failed, so that it reports as a
successful (skipped) required status check and does not block merging.

Selection SHALL be implemented with job-level `if:` conditions on the detection outputs, NOT with a
workflow-level `on.*.paths` / `paths-ignore` filter, because a workflow that is filtered out never
reports its required status checks and would leave a pull request permanently blocked.

#### Scenario: Frontend-only change skips pytest

- **WHEN** a pull request changes only files under `frontend/`
- **THEN** the `pytest` and `lint` jobs are skipped and the `frontend` job runs, and the pull
  request's required checks are all satisfied

#### Scenario: Python-only change skips frontend

- **WHEN** a pull request changes only Python-relevant files
- **THEN** the `frontend` job is skipped and the `pytest` and `lint` jobs run, and the pull
  request's required checks are all satisfied

#### Scenario: Docs-only change skips all test jobs

- **WHEN** a pull request changes only `openspec/` or `docs/` or Markdown files
- **THEN** the `pytest`, `lint`, `frontend`, and `docker` jobs are all skipped and the pull request
  is mergeable with all required checks satisfied

#### Scenario: A skipped required job does not block the merge

- **WHEN** a required-status-check job is skipped because its category did not change
- **THEN** the skipped job reports as success for branch protection and does not hold the pull
  request in a pending state
