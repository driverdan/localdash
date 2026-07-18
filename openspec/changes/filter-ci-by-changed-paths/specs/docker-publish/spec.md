## MODIFIED Requirements

### Requirement: Docker image is built in CI on every run

The CI workflow SHALL build the Docker image from the repository's `Dockerfile` on every
`pull_request` run and every push to `main` **whose diff could affect the image's contents** — that
is, whenever the `python` or `frontend` change category is present, or `Dockerfile` /
`docker-entrypoint.sh` changed. A run whose diff cannot affect the image (for example a
documentation-only change) SHALL skip the docker job, and the skipped job SHALL report as a
successful (skipped) required status check so it does not block merging. This ensures a change that
breaks the image build cannot merge unnoticed while avoiding a rebuild for changes the image is
blind to.

The docker job SHALL build when **either** the `pytest` or the `frontend` job ran (it SHALL NOT
require both), and SHALL NOT build if either test job failed or was cancelled.

#### Scenario: Pull request builds the image without pushing

- **WHEN** a pull request run executes the docker job
- **THEN** the image is built for `linux/amd64` but not pushed to any registry, and no registry
  credentials are required for the run to succeed

#### Scenario: Broken Dockerfile fails the pull request

- **WHEN** a pull request contains a change that makes the Docker image build fail
- **THEN** the docker job fails and the failure is reported on the pull request

#### Scenario: Single-sided change still builds the image

- **WHEN** a pull request changes only Python-relevant files (so `frontend` is skipped) or only
  `frontend/` files (so `pytest` is skipped)
- **THEN** the docker job still runs and builds the image, because at least one test job ran and
  neither failed

#### Scenario: Documentation-only change skips the build

- **WHEN** a pull request changes only files that cannot affect the image (for example under
  `openspec/` or `docs/`)
- **THEN** the docker job is skipped, reports as a successful required check, and no image is built

### Requirement: Images are pushed to Docker Hub only from green main builds

On pushes to `main`, the workflow SHALL push the built image to the `driverdan/localdash` Docker
Hub repository, and SHALL do so only when the docker job runs — that is, when neither the `pytest`
nor the `frontend` job failed or was cancelled and at least one of them ran (or `Dockerfile` /
`docker-entrypoint.sh` changed). It SHALL NOT require both test jobs to have run.

#### Scenario: Main push publishes after tests pass

- **WHEN** a push to `main` runs the workflow and every test job that ran (`pytest`, `frontend`, or
  both) succeeded
- **THEN** the docker job authenticates to Docker Hub using the `DOCKERHUB_USERNAME` and
  `DOCKERHUB_TOKEN` repository secrets and pushes the image

#### Scenario: Failing tests block the push

- **WHEN** a push to `main` runs the workflow and the `pytest` or `frontend` job fails
- **THEN** the docker job does not run and no image is pushed

#### Scenario: Single-sided main push publishes

- **WHEN** a push to `main` changes only Python-relevant files or only `frontend/` files, so one
  test job is skipped and the other succeeds
- **THEN** the docker job runs and pushes the image without waiting on the skipped job
