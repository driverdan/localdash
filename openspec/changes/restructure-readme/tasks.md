## 1. Capture the screenshot

- [x] 1.1 Bring up the full stack with `docker compose up --build` and let the
      scheduler complete at least one poll cycle so the Home digest widgets have
      real content
- [x] 1.2 Capture the Home page at `/` in the default light theme at a desktop
      viewport width
- [x] 1.3 Commit the image to `docs/images/` with a descriptive filename, and
      confirm nothing in `.gitignore` or `.dockerignore` excludes it

## 2. Write CONTRIBUTING.md

- [x] 2.1 Create `CONTRIBUTING.md` at the repo root with a short intro naming it
      as the human contributor guide
- [x] 2.2 Move the local-venv quick start from the README verbatim-in-substance
      (Dockerized DB, `uv sync --extra dev`, `.env` copy, `alembic upgrade head`,
      `uvicorn --reload`) and the frontend build/dev-server steps
- [x] 2.3 Move the Tests section, keeping the note that DB-backed tests skip
      unless `DATABASE_URL` points at a reachable Postgres
- [x] 2.4 Move the Linting & formatting section, keeping the once-per-clone
      `pre-commit install` note and the abort-on-reformat behavior
- [x] 2.5 Add a section linking to `AGENTS.md` for architecture and for the git /
      OpenSpec three-PR workflow, without restating either
- [x] 2.6 Verify every command in the file against the current `pyproject.toml`,
      `frontend/package.json`, and `.pre-commit-config.yaml`

## 3. Rewrite README.md

- [x] 3.1 Write the title and one-paragraph description, stating that built-in
      sources are Chattanooga / Hamilton County TN specific and that multi-city
      support is planned
- [x] 3.2 Embed the screenshot from task 1 by repository-relative path
- [x] 3.3 Write the features table covering Home (`/`), News (`/news`), Map
      (`/map`), and Events (`/events`), plus Weather and where it surfaces
- [x] 3.4 Write the ~4-line "how it works" summary of snapshot → time-series, with
      no hypertable, PostGIS, or JSONB detail
- [x] 3.5 List the four registered geo sources by human-readable name, linking to
      their `docs/*.md` references; do not list Weather among them
- [x] 3.6 Write the Docker quick start, keeping the `docker.sock` permission note
- [x] 3.7 Write the Configuration section pointing at `.env.example`, and note
      that `SITE_NAME` and the center coordinate are configurable
- [x] 3.8 Keep the Cloudflare named tunnel section, lightly trimmed, including the
      no-authentication warning
- [x] 3.9 Write the Contributing section linking to `CONTRIBUTING.md`,
      `AGENTS.md`, and the app's `/docs` API reference
- [x] 3.10 Keep the AGPL-3.0-or-later license section
- [x] 3.11 Delete the removed sections: the Map deep dive, the data model table,
      the four API endpoint tables, "Adding a geo data source", Git workflow, and
      the local-dev / Tests / Linting sections now in `CONTRIBUTING.md`
- [x] 3.12 Fold the surviving Notes bullets (good-upstream-citizen, retention)
      into Configuration and drop the `X-Frontend-Auth` reference entirely

## 4. Correct AGENTS.md

- [x] 4.1 Confirm the "What this is" section describes four features including
      Weather with no DB tables and no scheduler job, and correct it if not
- [x] 4.2 Update any cross-reference in `AGENTS.md` that points at README sections
      this change removed

## 5. Verify against the specs

- [x] 5.1 Check the drift audit table in `design.md` item by item and confirm each
      correction landed in the rewritten README
- [x] 5.2 Grep the README for `X-Frontend-Auth`, `/api/active`, `/api/ws/live`,
      `/api/sources`, and `/api/v1/timeseries/ws` and confirm no hits
- [x] 5.3 Confirm every configuration setting named in the README exists in
      `app/config.py`
- [x] 5.4 Follow every relative link in `README.md` and `CONTRIBUTING.md` and
      confirm each target exists
- [x] 5.5 Start the app and confirm `/docs` loads, since the README now relies on
      it as the API reference
- [x] 5.6 Run `pre-commit run --all-files` so prettier formats the new and
      rewritten Markdown
- [x] 5.7 Run `openspec validate restructure-readme --strict`
