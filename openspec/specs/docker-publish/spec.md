# docker-publish Specification

## Purpose

CI-driven Docker image build and publication. The `docker` job in `.github/workflows/tests.yml`
builds the production image with buildx on every CI run — so a Dockerfile break can never merge —
and pushes tagged images to the `driverdan/localdash` Docker Hub repository only from pushes to
`main` that passed the test jobs. Authentication uses the `DOCKERHUB_USERNAME` /
`DOCKERHUB_TOKEN` repository secrets (a Docker Hub access token, not the account password);
pull-request runs never touch credentials.

## Requirements

### Requirement: Docker image is built in CI on every run

The CI workflow SHALL build the Docker image from the repository's `Dockerfile` on every
`pull_request` run and every push to `main`, so that a change that breaks the image build cannot
merge unnoticed.

#### Scenario: Pull request builds the image without pushing

- **WHEN** a pull request run executes the docker job
- **THEN** the image is built for `linux/amd64` but not pushed to any registry, and no registry
  credentials are required for the run to succeed

#### Scenario: Broken Dockerfile fails the pull request

- **WHEN** a pull request contains a change that makes the Docker image build fail
- **THEN** the docker job fails and the failure is reported on the pull request

### Requirement: Images are pushed to Docker Hub only from green main builds

On pushes to `main`, the workflow SHALL push the built image to the `driverdan/localdash` Docker
Hub repository, and SHALL do so only after the `pytest` and `frontend` jobs have succeeded in the
same workflow run.

#### Scenario: Main push publishes after tests pass

- **WHEN** a push to `main` runs the workflow and the `pytest` and `frontend` jobs succeed
- **THEN** the docker job authenticates to Docker Hub using the `DOCKERHUB_USERNAME` and
  `DOCKERHUB_TOKEN` repository secrets and pushes the image

#### Scenario: Failing tests block the push

- **WHEN** a push to `main` runs the workflow and the `pytest` or `frontend` job fails
- **THEN** the docker job does not run and no image is pushed

### Requirement: Published images are tagged latest and by commit SHA

Every image pushed from `main` SHALL carry the `latest` tag and a tag derived from the commit SHA,
so that `latest` tracks the newest green commit while each published build remains individually
pullable for rollback.

#### Scenario: Tags on a published image

- **WHEN** an image is pushed from a `main` build of commit `abc1234...`
- **THEN** Docker Hub receives the same image as both `driverdan/localdash:latest` and a SHA tag
  referencing `abc1234` (short form)

### Requirement: Build layers are cached between runs

The docker job SHALL use the GitHub Actions cache backend for buildx layer caching, covering all
build stages, so dependency-installation layers are reused when `frontend/package-lock.json` and
`uv.lock` are unchanged.

#### Scenario: Unchanged lockfiles reuse cached layers

- **WHEN** a run builds the image and no dependency lockfile has changed since the previous
  cached build
- **THEN** the npm and uv dependency layers are restored from cache rather than rebuilt
