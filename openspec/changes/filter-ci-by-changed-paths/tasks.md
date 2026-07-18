## 1. Change-detection job

- [x] 1.1 Add a `changes` job to `.github/workflows/tests.yml` that runs `dorny/paths-filter` (pinned to a major tag, e.g. `@v3`) and defines `python`, `frontend`, and `docker` filters per the design, each also matching `.github/workflows/tests.yml`.
- [x] 1.2 Expose the filter results as job outputs (`python`, `frontend`, `docker`) so downstream jobs can read `needs.changes.outputs.*`.
- [x] 1.3 Ensure the job has the permissions/config `paths-filter` needs to diff both `pull_request` (base…head) and `push` (before…after) events.

## 2. Gate the test jobs

- [x] 2.1 Add `needs: [changes]` and `if: needs.changes.outputs.python == 'true'` to the `pytest` job.
- [x] 2.2 Add `needs: [changes]` and `if: needs.changes.outputs.frontend == 'true'` to the `frontend` job.

## 3. Rework the docker job

- [x] 3.1 Change the docker job's `needs` to `[changes, pytest, frontend]`.
- [x] 3.2 Replace the implicit `needs`-both-succeed gating with the guard `if: !cancelled() && !failure() && (python || frontend || docker changed)` so it builds when either test job ran and neither failed.
- [x] 3.3 Confirm the existing `push`-event conditions on the Docker Hub login and `push:` steps are unchanged (fork PRs stay credential-free; publish still only on `main`).

## 4. Verify behavior

- [x] 4.1 Validate the change: `openspec validate filter-ci-by-changed-paths`.
- [x] 4.2 Confirm YAML parses (e.g. `actionlint` or a workflow lint) and the `if:` expressions are well-formed.
- [x] 4.3 Open a docs-only PR (`openspec/` or `*.md`) and confirm `pytest`, `frontend`, and `docker` all skip and report green under required checks.
- [x] 4.4 Open a `frontend/`-only PR and confirm `pytest` skips while `frontend` and `docker` run.
- [x] 4.5 Open an `app/`-only PR and confirm `frontend` skips while `pytest` and `docker` run.
- [x] 4.6 Confirm a PR editing `.github/workflows/tests.yml` runs all three jobs.
