## 1. Workflow job

- [x] 1.1 Add a `docker` job to `.github/workflows/tests.yml` with `needs: [pytest, frontend]`,
      running on `ubuntu-latest`
- [x] 1.2 Set up buildx (`docker/setup-buildx-action`) and log in to Docker Hub
      (`docker/login-action` with `DOCKERHUB_USERNAME`/`DOCKERHUB_TOKEN` secrets), with login
      conditioned on `github.event_name == 'push'` so PR runs never touch secrets
- [x] 1.3 Generate tags with `docker/metadata-action` for image `driverdan/localdash`: `latest`
      on the default branch plus a short-SHA tag (`type=sha`)
- [x] 1.4 Build with `docker/build-push-action`: `platforms: linux/amd64`,
      `push: ${{ github.event_name == 'push' }}`, tags/labels from the metadata step, and GHA
      layer caching (`cache-from: type=gha`, `cache-to: type=gha,mode=max`)

## 2. Verification

- [x] 2.1 Validate the workflow YAML locally (e.g. `actionlint` or a YAML parse) before opening
      the PR
- [x] 2.2 Open the phase PR and confirm the PR run builds the image without pushing and without
      needing secrets
- [ ] 2.3 After merge, confirm the main run pushes `driverdan/localdash:latest` and the SHA tag
      to Docker Hub

## 3. Manual setup (outside the repo)

- [ ] 3.1 Create the `driverdan/localdash` repository on Docker Hub and generate a read/write
      access token
- [ ] 3.2 Add `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` secrets to the GitHub repository
      (needed before the first main push; PR builds work without them)
