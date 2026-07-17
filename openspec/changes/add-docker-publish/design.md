## Context

The repository already has a multi-stage `Dockerfile` (Node frontend build → uv dependency stage →
slim Python runtime) and a `.github/workflows/tests.yml` workflow with two jobs (`pytest`,
`frontend`) that runs on pull requests and pushes to `main`. Nothing in CI builds the Docker image,
and no image is published anywhere. The repo is public (`driverdan/localdash`), so Actions minutes
are free and unmetered.

## Goals / Non-Goals

**Goals:**

- Publish `driverdan/localdash` to Docker Hub on every push to `main` that passes tests.
- Exercise the Dockerfile in CI on every pull request (build only, no push).
- Reuse buildx layer caching across runs so dependency layers (npm ci, uv sync) are not rebuilt
  when lockfiles are unchanged.

**Non-Goals:**

- Multi-architecture images — `linux/amd64` only (the deploy target; can be revisited later).
- Semver/release tagging — there is no versioning scheme in the repo; `latest` + SHA is enough.
- Changing `docker-compose.yml` to pull the published image instead of building locally.
- Publishing to GHCR or any registry other than Docker Hub.

## Decisions

### Job in `tests.yml`, not a separate workflow

The build/push runs as a `docker` job inside the existing `tests.yml` with
`needs: [pytest, frontend]`. A separate workflow triggered on `push` to main would run regardless
of test outcomes, and gating it would require the clunkier `workflow_run` trigger with its detached
status reporting. `needs` inside one workflow is the direct expression of "push only after green
tests", and the existing workflow already has the right triggers (`pull_request` + `push` to main).
The workflow's display name should change from "Tests" to something broader (e.g. "CI") only if
desired — not required, and renaming churns branch-protection contexts, so the name stays.

### Push condition: event type, not branch check

The job always builds; the push step is enabled with `push: ${{ github.event_name == 'push' }}`.
Because the workflow's `push` trigger is already filtered to `branches: [main]`, the event name
alone is sufficient — no separate ref check needed. On `pull_request` events the same build runs
with `push: false`, which validates the Dockerfile without credentials. Login to Docker Hub is
likewise conditioned on the event so PR runs never touch secrets (secrets are unavailable to
fork PRs anyway, and skipping login keeps fork PR builds green).

### Standard Docker actions, tags from `metadata-action`

Use the canonical chain: `docker/setup-buildx-action` → `docker/login-action` →
`docker/metadata-action` → `docker/build-push-action`. `metadata-action` generates the two tags —
`latest` (on the default branch) and the commit SHA (`type=sha`, prefixed `sha-`) — plus OCI labels
for provenance. Hand-rolling tag strings buys nothing over the maintained action.

### Caching: `type=gha`

`cache-from: type=gha` / `cache-to: type=gha,mode=max` stores buildx layers in the GitHub Actions
cache. `mode=max` caches all stages (including the frontend and deps build stages), which is the
point — those are the expensive layers. Alternative considered: registry cache
(`type=registry`) pushed to Docker Hub; rejected because it pollutes the public repo with cache
artifacts and GHA cache is simpler with equivalent hit rates for a single-runner setup.

### Credentials: repository secrets with an access token

`DOCKERHUB_USERNAME` + `DOCKERHUB_TOKEN` repository secrets, where the token is a Docker Hub
access token scoped to read/write (never the account password — tokens are revocable
independently). Docker Hub has no OIDC federation with GitHub Actions, so unlike GHCR there is no
tokenless option.

### Concurrency: leave the existing group alone

The workflow's existing `concurrency` group already includes the ref, so main pushes are never
cancelled and PR pushes cancel superseded runs — exactly the semantics the docker job needs too.
Two rapid pushes to main run to completion in order of scheduling; a momentarily stale `latest` is
acceptable for this project and the SHA tags are always correct.

## Risks / Trade-offs

- [Two rapid main pushes could finish out of order, leaving `latest` pointing at the older commit]
  → SHA tags are always correct; the next main push heals `latest`. Not worth serializing with a
  dedicated concurrency group for a single-maintainer repo.
- [GHA cache eviction (7-day / 10 GB) causes occasional full rebuilds] → Acceptable; a cold build
  is a few minutes. `mode=max` increases cache size but the image has few, small stages.
- [Docker Hub rate limits or outages fail the push after tests pass] → The job is independent of
  the test jobs' status reporting; re-run the failed job from the Actions UI.
- [Secrets not yet configured when the workflow first lands] → The PR run doesn't need them
  (build-only); the first main push will fail at login with a clear error until the two secrets
  are added. Called out in tasks as a manual step.

## Open Questions

None — registry, gating, platforms, and tagging were settled during exploration.
