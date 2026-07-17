## Why

The Docker image is only ever built locally via `docker compose up --build` — nothing in CI builds
it, so a Dockerfile break can merge unnoticed, and there is no published image others (or another
machine) can pull without cloning the repo and building from source. Publishing to Docker Hub on
every main update gives a deployable artifact that is guaranteed to have passed the test suite.

## What Changes

- Add a `docker` job to the existing `.github/workflows/tests.yml` workflow that builds the image
  with buildx and pushes it to Docker Hub as `driverdan/localdash`.
- Pushes happen only on pushes to `main`, and only after the existing `pytest` and `frontend` jobs
  succeed (`needs`) — the image push is gated on green tests.
- On pull requests the same job builds the image without pushing, so a broken Dockerfile cannot
  merge (this closes the current gap where CI never exercises the Dockerfile at all).
- Images are tagged `latest` and with the commit SHA; builds target `linux/amd64` only.
- Buildx layer caching via the GitHub Actions cache backend so the npm/uv dependency layers are
  reused between runs.
- Requires two new repository secrets: `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` (a Docker Hub
  access token, not the account password) — configured outside the repo.

## Capabilities

### New Capabilities

- `docker-publish`: CI-driven Docker image build and publication — building the image on every PR
  and push to main, and pushing tagged images to Docker Hub only from main after tests pass.

### Modified Capabilities

<!-- none — no existing capability covers CI workflows -->

## Impact

- `.github/workflows/tests.yml`: new `docker` job (workflow-level `permissions` and `concurrency`
  unchanged; the job needs no write permissions since it authenticates to Docker Hub via secrets).
- Docker Hub: new public repository `driverdan/localdash` receiving `latest` + per-commit SHA tags.
- GitHub repository settings: two new Actions secrets (`DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`).
- No application code, Dockerfile, or docker-compose changes.
