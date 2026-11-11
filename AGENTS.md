# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

LocalDash is a local-data dashboard with four features (composed into a widget-digest home page
at `/` by the frontend's `home` feature):

- **Timeseries** (`/map`): stores, serves, and views **time-series geolocation data** — active 911
  incidents for Hamilton County TN, TDOT SmartWay roadway events, EPB outages, and TN American Water
  advisories. The geo stack is deliberately source-agnostic so APRS / weather / other geo feeds can
  be added without schema changes.
- **News** (`/news`): an RSS aggregator for Chattanooga outlets that clusters articles
  covering the same story across outlets (ported from the standalone ChattNews app). Not a geo
  source — it is a sibling feature beside the timeseries pipeline, not a collector ("sibling"
  describes the data pipeline, not an import boundary; see "Backend code organisation").
- **Events** (`/events`): aggregates, de-duplicates, tags, and geocodes local happenings (The
  Pulse's CitySpark calendar, car cruises, the Chattanooga Zoo, Meetup groups, configurable iCal
  calendars, The Events Calendar (tribe) WordPress calendars — by default the Chattanooga Public
  Library's; ported from the `chattevents` PoC). Also a
  sibling feature — events are merged cross-source records, not entity-state-over-time, so they do
  not flow through collectors/ingest.
- **Weather** (the homepage strip): current conditions + today's forecast proxied from the
  National Weather Service API, plus air quality from AirNow when an API key is set. The smallest
  feature by design — no DB tables, just an in-process TTL cache kept current by one scheduled
  refresh job; also a sibling feature, not a collector (weather-on-the-map as a
  geo feed remains a separate future idea).

## Tech stack & why

**Data store — Postgres + PostGIS + TimescaleDB** (one image: `timescale/timescaledb-ha:pg16`).
- *PostgreSQL*: relational base with strong JSONB support, which the schema leans on for
  source-specific fields (no per-source migrations).
- *PostGIS*: real geospatial types + indexes; geometry is stored as arbitrary
  `geometry(Geometry,4326)` (points and polygons), and the API does bbox / `ST_Intersects` queries
  rather than filtering in Python.
- *TimescaleDB*: turns `observations` into a hypertable partitioned on `observed_at`, giving the
  time-series side scalable inserts/scans (and room for retention policies — none is configured
  yet; history is kept forever). The HA image
  bundles PostGIS + TimescaleDB so a single container covers both.

**Web layer — FastAPI + Uvicorn.** Chosen because the app is fundamentally async (concurrent source
polling, an HTTP client, and a push WebSocket). FastAPI's native async, dependency injection (used for
DB sessions), Pydantic integration, and first-class WebSocket support fit that model with little glue.

**ORM / DB drivers — SQLAlchemy 2.0 (async) + asyncpg, plus psycopg for Alembic.**
- *SQLAlchemy 2.0 async* for the app's queries; *asyncpg* is the fastest async Postgres driver.
- *GeoAlchemy2* maps PostGIS geometry columns into SQLAlchemy.
- *psycopg (v3, binary)* is a **second, synchronous** driver used only by Alembic (migrations run
  synchronously). This is why `config.py` derives a sync URL from the async one — see the
  "Two DB drivers" note below.

**Migrations — Alembic**, but with **hand-written raw SQL** because PostGIS extensions, the
`create_hypertable()` call, and GIST indexes don't round-trip through autogenerate.

**Scheduling — APScheduler (AsyncIOScheduler).** An in-process async scheduler runs the poll loop inside
the FastAPI event loop — one job per geo collector plus one job each for news, events, and weather
refresh. Deliberately avoids a
separate worker + broker (Celery/Redis): at this scale a background task is simpler and has no extra
moving parts.

**HTTP client — httpx.** Async client for fetching upstream sources, matching the async stack (and the
same library FastAPI's TestClient builds on). Every outbound client comes from `make_client` in
`app/http.py`, and each call passes its timeout and redirect policy explicitly. The User-Agent
defaults to the `user_agent` setting, whose default `DEFAULT_USER_AGENT` is the browser UA with
` LocalDash/0.1` appended (a real browser string that still identifies us); pass `user_agent=` only to override it with a UA the upstream
requires (today: `BROWSER_USER_AGENT` for CarCruiseFinder and the news HTML scrape, the geocoder's
own setting for Nominatim; `tests/test_http.py` enforces that list). No request sends httpx's
default `python-httpx/…` or an empty UA, and a blank override raises. `tests/test_http_wire.py`
pins each upstream's values. Tests fake upstreams with
the `mock_http` fixture (`mock_http.install(handler)`; sent requests in `mock_http.requests`). Any
outbound request a test doesn't mock is refused and fails the test, even if the code swallows it.

**RSS parsing — feedparser** (plus **BeautifulSoup** for the one `kind: html` news feed and the
events scrapers). feedparser is synchronous, so the news fetcher runs it in `asyncio.to_thread`;
kept over an httpx rewrite because its redirect/encoding/entity handling is what the ported
ChattNews behavior was tuned against.

**Config / validation — Pydantic v2 + pydantic-settings.** Typed settings loaded from env/`.env`, and
`NormalizedObservation` is a Pydantic model so collector output is validated at the boundary.

**Python dependency locking — uv (`uv.lock`).** The project stays plain PEP 621: uv owns no
metadata in `pyproject.toml`, so `pip install -e ".[dev]"` keeps working and uv is removable by
deleting one file. It is used for the one thing pip cannot do here — produce a **universal**
lock. `uv.lock` carries environment markers covering the `requires-python = ">=3.14"` range and
Linux/macOS/Windows, so one file serves every machine that builds this repo — Docker, CI, and local
venvs all run 3.14, but they do not all run the same OS. The standard `pylock.toml` was the obvious
alternative and was rejected on three counts: `pip lock` is experimental and self-describes as
removable without warning; its output resolves against *one* environment, so a lock built on Linux
pins `manylinux` wheels and hard-fails on macOS; and Dependabot cannot
read it ([dependabot-core#12094](https://github.com/dependabot/dependabot-core/issues/12094)),
which would leave the lock silently stale on every bump PR it opens. uv is a build-time tool only —
the Dockerfile's `deps` stage produces `/app/.venv` and the runtime image copies it without the uv
binary, the same split that keeps Node out of the runtime image.

**Frontend — Svelte 5 + TypeScript + Leaflet, built by plain Vite (not SvelteKit).** Source lives in
`frontend/`; `vite build` outputs into `static/`, which is a **gitignored build artifact** served by
FastAPI's existing mount (never edit `static/` by hand). Svelte's runes replace the old vanilla-JS
state↔DOM plumbing; SvelteKit was rejected because FastAPI is the server and the app is one static
SPA. Leaflet + markercluster are npm deps (typed, bundled — no CDN); the map is driven imperatively
inside `MapView.svelte`, not through marker components. Marker icons are CSS `divIcon`s, so there are
no image assets to manage. Node is needed only to build the frontend, never at runtime (multi-stage
Dockerfile).

The frontend lays out its source by the API's feature namespaces and adds import rules of its
own (the backend has no matching rules): each feature owns
`frontend/src/features/<feature>/` (`home` on `/`, `news` on `/news`, `timeseries` on `/map` — it
owns the Leaflet map — and `events` on `/events`), composed per-route by `App.svelte`;
feature-agnostic shell code lives in `frontend/src/lib/`. Routing is a **tiny hand-rolled path
router** (`lib/router.svelte.ts`: reactive path + `pushState` + `popstate` — four routes don't
justify a dependency), backed by an SPA fallback in `main.py`'s static mount (extension-less
non-`/api` 404s serve `index.html` so `/map` deep-links).
**Import rules:** features import from `lib/`, themselves, and other features' `index.ts` public
surfaces only (e.g. `home` reuses the news card) — never another feature's internals; the shell
imports only each feature's `index.ts`; `lib/` imports from no feature. Adding a frontend feature =
new folder + shell-level wiring: import its `index.ts` and add a route entry and nav link in
`App.svelte`, import its stylesheet in `main.ts`, and (if it listens to the live bus) call its
`register*Live()` in `App.svelte` — the counterpart of "new router + one `include_router` line".

**Packaging / runtime — Docker Compose.** One command brings up DB + app; the app container waits on the
DB healthcheck, runs migrations, then serves. Keeps "works on my machine" out of the loop.

## Agent co-authorship (all commits and PRs)

Any agent making a git commit or opening a GitHub PR in this repo **must** add
itself as a co-author so the work is attributable to the tool and model that
produced it, not just the human operator.

For **git commits**, append a `Co-Authored-By:` trailer to the commit message
(multi-line, after a blank line) identifying the agentic tool and the model it
ran on, plus the standard name/email pair:

```
<commit subject>

<body>

Co-Authored-By: <Tool> (<model>) <noreply@agent.local>
```

- `<Tool>` is the agentic tool you are (e.g. `pi`, `Claude Code`, `Codex`,
  `Cursor`).
- `<model>` is the model identifier you are running on (e.g.
  `claude-sonnet-4.5`, `gpt-5`, `gemini-2.5-pro`).
- Use the `noreply@agent.local` email so GitHub doesn't try to match a real
  account; if your tool exposes a configured git identity, prefer that.

Example:

```
Add APRS collector

Polls the APRS-IS feed every 60s and normalizes positions into
NormalizedObservation with source_key='aprs'.

Co-Authored-By: pi (claude-sonnet-4.5) <noreply@agent.local>
```

For **GitHub PRs**, add the same `Co-Authored-By:` trailer in
the PR description, e.g.:

> Co-Authored-By: pi (claude-sonnet-4.5) <noreply@agent.local>

This applies to *every* commit and PR an agent creates — OpenSpec phase PRs,
fixes, chores, everything — regardless of whether the change follows the
OpenSpec workflow below. Do not omit it even for one-line commits.

## Git workflow (OpenSpec, three PRs)

Changes that are large enough to warrant a written plan use **OpenSpec**
(`openspec/`) and land as **three sequential pull requests**, one per phase of
the OpenSpec lifecycle. Never commit directly to `main`. Start every phase on a
new branch with a semantic name.

The change directory lives at `openspec/changes/<name>/` and is archived to
`openspec/changes/archive/YYYY-MM-DD-<name>/` at the end. Each PR below owns one
lifecycle phase; do not mix code into the proposal PR or planning artifacts into
the implementation PR.

These PRs should be opened automatically upon completing the openspec step. No
user input or confirmation is needed to open the PR.

### PR 1 — Proposal (planning artifacts only)

Create the change and generate its artifacts, then open a PR that contains **only
planning files** — no implementation code yet.

1. `openspec new change "<name>"` (kebab-case, e.g. `add-aprs-collector`), then
   drive each artifact to `done` with the openspec-propose flow
   (`openspec status --change "<name>" --json`, `openspec instructions
   <artifact-id> --change "<name>" --json`). Artifacts produced: `proposal.md`,
   `design.md`, `tasks.md`, and delta `specs/`.
2. On a branch named for the change (e.g. `add-aprs-collector`), commit the new
   `openspec/changes/<name>/` directory and push.
3. Open PR #1. **Review focus:** is the proposal sound, the design coherent, and
   the task list complete? No code here — if the plan needs revising, use the
   openspec-update-change flow and push more commits to this same PR before
   merging.

### PR 2 — Implementation (code review)

After PR #1 merges, implement the tasks and open a PR that contains **only code**
plus the checked-off task list.

1. From `main`, branch again (e.g. `add-aprs-collector-impl`). Run the
   openspec-apply-change flow (`openspec instructions apply --change "<name>"
   --json`) and work through `tasks.md`, marking each `- [ ]` → `- [x]` as you
   go. Keep changes minimal and scoped to each task.
2. Commit code + the updated `tasks.md` checkbox state. Do **not** edit
   `proposal.md` / `design.md` / `specs/` here — if implementation reveals a
   plan gap, pause, revise artifacts on the proposal branch instead (see
   openspec-update-change), and re-open or amend as needed.
3. Open PR #2. **Review focus:** does the code match the agreed plan, and are all
   tasks checked off? Merge only when `openspec status --change "<name>"` shows
   all tasks complete.

### PR 3 — Archive (finalize the change)

After PR #2 merges, finalize the change: sync delta specs to the main specs and
move the change directory into the archive.

1. From `main`, branch (e.g. `add-aprs-collector-archive`). Run the
   openspec-archive-change flow. If delta specs exist, sync them into
   `openspec/specs/` (openspec-sync-specs) — this updates the canonical specs
   and should land in this same PR. Then `openspec archive` (or the equivalent
   move) relocates `openspec/changes/<name>/` →
   `openspec/changes/archive/YYYY-MM-DD-<name>/`.
2. Commit the spec updates + the archive move together and push.
3. Open PR #3. **Review focus:** were the delta specs merged into the main specs
   correctly, and was the change moved to the dated archive directory? Merge,
   and the change is fully closed out.

## Commands

**Run the full stack (app + Postgres) in Docker:**
```bash
docker compose up --build        # app waits for DB health, runs migrations, then serves :8000
```
Home digest at http://localhost:8000/, news at http://localhost:8000/news, map dashboard at
http://localhost:8000/map, events at http://localhost:8000/events. The app container loads an
optional `.env` (`env_file`), so `.env` settings apply under Docker too; `DATABASE_URL` is pinned
to the in-network `db` host.

**Local dev (Dockerized DB, app from venv with --reload):**
```bash
docker compose up -d db
uv sync --extra dev               # creates/updates .venv from uv.lock; add --locked to fail on a stale lock
source .venv/bin/activate         # or prefix commands with `uv run`
cp .env.example .env              # DATABASE_URL -> localhost:5432
alembic upgrade head
uvicorn app.main:app --reload
```
`pip install -e ".[dev]"` still works — pyproject.toml is plain PEP 621 with no uv-specific
tables — but it resolves fresh instead of reading `uv.lock`, so you can silently get versions CI
and Docker never test. Prefer `uv sync`.

**Dependencies (`pyproject.toml` + `uv.lock`, both committed):**
```bash
uv lock --upgrade-package fastapi  # bump one dep to the newest its declared range allows
uv lock --upgrade                  # re-resolve everything within the declared ranges
uv lock                            # after hand-editing pyproject.toml — never leave the lock stale
```
Direct deps are pinned with **bounded ranges** — `~=X.Y.Z` (that patch series only) or
`>=A,<B` (an explicit upper bound, often spanning a few minors) — so anything past the bound is
opted into by editing `pyproject.toml`, never picked up by an install. Widening a range is the
deliberate act; `uv lock` then records the exact transitive set. **Any change to
`pyproject.toml` dependencies must be followed by `uv lock`** — CI and the Docker build install
with `uv sync --locked`, which errors on a lock that disagrees with pyproject, so a skipped re-lock
blocks the merge rather than drifting. Check it yourself with `uv lock --check`.

⚠️ The guard flag is **`--locked`, not `--frozen`**. They read alike and do different things:
`--locked` verifies `uv.lock` against `pyproject.toml` and fails if it is stale; `--frozen` skips
that check and installs the lock as-is, so a dependency edit with no re-lock passes silently. Use
`--frozen` only where you deliberately want the lock honored without consulting pyproject.

**Frontend (source in `frontend/`, builds into gitignored `static/`):**
```bash
cd frontend
npm install                       # once
npm run dev                       # hot-reload dev server :5173, proxies /api (+ WS) to :8000
npm run build                     # build into ../static (what uvicorn/Docker serve)
npm run check                     # svelte-check: strict TypeScript gate, must stay at 0 errors
```
The Docker image builds the frontend itself (multi-stage); local `uvicorn` serves whatever
`static/` build is present, so run `npm run build` after frontend changes when not using `npm run dev`.

**Tests:**
```bash
pytest                                            # full suite
pytest tests/test_ingest.py::test_state_changed_status_transition   # single test
```
Most tests are pure/offline. The DB-backed tests (the DB cases in `tests/test_ingest.py`,
`tests/test_api_timeseries.py`, `tests/test_news_db.py`, and the events DB tests in
`tests/test_events_ingest.py`, `tests/test_api_events.py`, and `tests/test_events_cityspark.py`, via
the `db_session` / `news_db_session` / `events_db_session` fixtures in `conftest.py`) never touch
the app's database. Each run creates a temporary `localdash_test_<epoch>_<rand>` database on the
server named by `DATABASE_URL`, migrates it with `alembic upgrade head` (in a subprocess), empties
every table before each DB-backed test, and drops it when the run ends. Databases left behind by
killed runs are dropped by a later run once they are over an hour old. `conftest.py` overrides
`DATABASE_URL` before any `app.*` import, so app code that opens its own sessions (the global
`SessionLocal` in `refresh()` and the scheduler) uses the temporary database too. Keep that override
first in `conftest.py`. Every truncate and drop refuses to run on a database whose name doesn't start
with `localdash_test`. Bring up `docker compose up -d db` first; the role in `DATABASE_URL` needs
`CREATE DATABASE` and the right to create the PostGIS and TimescaleDB extensions (the compose
superuser has both). If the server is unreachable or migration fails, DB-backed tests **fail**
rather than skip. Pure tests don't request a DB fixture, so they still run without Postgres. Seed
everything a DB test asserts on and assert exact values: the database starts empty. If the code
under test compares dates against the current time (e.g. `reconcile_events()` only sees upcoming
events), compute test dates relative to now or inject a fixed "now"; never hard-code future dates.

**CI:** `.github/workflows/tests.yml` runs on every PR and on pushes to `main`. A `changes` job
path-filters the diff (`dorny/paths-filter`) and the other jobs run only when their area changed —
a job skipped via its `if:` still reports success, so required checks never deadlock on a
docs-only PR. The jobs:

- **`pytest`** — the full suite. CI stands up the same `timescale/timescaledb-ha:pg16` image as a
  service container; the suite creates and migrates its own temporary database there, and the
  DB-backed tests fail (not skip) if it's unreachable, so CI can't go green on the offline subset
  alone. The job also `mkdir -p static`
  first — `static/` is a gitignored build artifact and `main.py` mounts it at import time, so a fresh
  checkout can't even import the app without it. Installs are `uv sync --locked`, which makes the
  job double as the lockfile gate: a `pyproject.toml` dependency edit without a matching `uv lock`
  fails here instead of merging a stale lock.
- **`frontend`** — `npm run check` + `npm run build`. There is **no JS test suite** (no runner, no
  `*.test.ts`), so these stand in as the frontend gate; they're what catches a bad npm bump, which
  `pytest` never sees. If a JS test runner is ever added, wire `npm test` into this job.
- **`docker`** — builds the production image whenever Python, frontend, or image files changed, so
  a broken Dockerfile can't merge. It runs after the test jobs and never when one failed. On pushes
  to `main` it also pushes `driverdan/localdash:latest` plus a `sha-<commit>` tag to Docker Hub; PR
  runs build without credentials or pushing.

**Linting & formatting (pre-commit):** a git pre-commit hook auto-fixes and lints **staged**
code — `ruff check --fix` + `ruff format` for Python, `prettier` for `frontend/`. Enable it once
per clone (hooks are not installed automatically):
```bash
uv sync --extra dev               # installs pre-commit + ruff into the venv
cd frontend && npm install        # prettier + prettier-plugin-svelte (also needed for builds)
pre-commit install                # from the repo root — wires .git/hooks/pre-commit
```
Behavior is **fix-then-abort**: if a hook rewrites a file the commit fails, leaving the fixes in
the working tree for you to review, re-stage, and re-commit — auto-fixes are never silently
committed. Config lives in `[tool.ruff]` (`pyproject.toml`), `frontend/.prettierrc`, and
`.pre-commit-config.yaml`. `ruff` is self-provisioned by pre-commit; `prettier` reuses
`frontend/node_modules`. Run against everything with `pre-commit run --all-files`; format the
frontend directly with `npm run format`.

`svelte-check` is deliberately **not** in the hook (it's a whole-project type checker, not a
per-file linter) — keep running it as `npm run check`. **Known gap:** the hook is bypassable with
`git commit --no-verify` and lint/format still has no CI backstop, so it remains a convenience
rather than an enforcement boundary. A CI `pre-commit run --all-files` job is deferred to a later
change. Keep the hook's ruff `rev` in step with the ruff version in `uv.lock` so the hook and a
manual `uv run ruff format` agree; `openspec/` is excluded from ruff because ruff ≥ 0.17 also
formats Python code blocks in Markdown and would rewrite archived artifacts.

**Migrations:** `alembic upgrade head` / `alembic revision -m "msg"`. The schema uses PostGIS +
TimescaleDB features that don't autogenerate, so migrations are hand-written **raw SQL** (see
`alembic/versions/0001_initial.py`).

## Architecture — the big picture

### The central idea: snapshot → time-series
The upstream 911 endpoint (`hc911server.com/api/calls`) returns only a **snapshot of currently-active
calls**, not history. LocalDash *constructs* the time-series itself. Understanding this requires reading
`collectors/`, `ingest.py`, and `scheduler.py` together:

1. **`scheduler.py`** polls each source on an interval (APScheduler, started in `main.py`'s lifespan).
2. **`collectors/`** fetch + normalize one source's payload into source-agnostic
   `NormalizedObservation`s. `ingest.py` never knows about source specifics.
3. **`ingest.py`** reconciles each batch against stored state:
   - upsert the `entity` (keyed by `source_key` + `external_id`; for 911, `external_id` =
     `master_incident_id`); ingest writes the normalized status into the entity's
     `latest_properties["status"]`, which the next poll's change detection reads,
   - **append an `observation` only when state changed** (status moved, or the geometry
     fingerprint changed — coordinates rounded to ~0.1 m, so point jitter is ignored) — this is
     what avoids one duplicate row per poll, and is the core of the time-series,
   - **closure sweep**: entities that were active but are absent from this payload are flipped
     `is_active=false` (with `last_seen_at` set to the close time) and get a final `Closed`
     observation. A successful fetch that normalizes to nothing therefore closes every active
     entity of that source — only a raised fetch error leaves them alone.
   - returns a `Diff` (`new`/`updated`/`closed`).
4. The scheduler broadcasts that `Diff` over the **global `/api/v1/ws` WebSocket bus** (`ws.py`,
   endpoint in `app/api/root.py`) as a `{topic: "timeseries", type: "diff"}` message; the frontend
   applies it incrementally. The same bus carries payload-free `{topic, type: "updated"}` pings for
   news/events/weather, which the frontend answers by refetching over REST.

### Non-obvious decisions
- **`observed_at` is the poll time, not the source's timestamp.** The feed uses a `1900-01-01` sentinel
  for missing `statusdatetime`, which would corrupt the series. Source timestamps are preserved inside
  `properties` (and `NormalizedObservation.source_time`). If you ever key the hypertable off source time,
  this is the thing to change (`ingest.py`).
- **Two DB drivers.** The app uses async `asyncpg`; Alembic uses sync `psycopg`. `config.py`'s
  `database_url_sync` derives the sync URL by string-swapping the driver. `DATABASE_URL` is always the
  **async** form.
- **`observations` is a TimescaleDB hypertable** on `observed_at`; its primary key is
  `(entity_id, observed_at)` because Timescale requires the partition column in the PK.

### Source-agnostic data model (`models.py`)
- `sources` — one row per registered source + last-run telemetry (written by `scheduler._record_run`).
- `entities` — one tracked thing per source; latest snapshot, `is_active`, `last_geom`,
  `geom_fingerprint` (change detection), `latest_properties`. Unique on `(source_key, external_id)`.
- `observations` — the hypertable; PostGIS `geom` (any geometry — points for 911/TDOT/EPB, polygons
  for `tnaw` advisories; migration `0006`) + JSONB `properties`. Source-specific fields
  live in JSONB so new sources need no migration.

### Adding a data source
Write a `BaseCollector` subclass in `app/collectors/<name>.py` (implement async `fetch()` and pure
`normalize()`), then register it in `app/collectors/__init__.py`'s `build_collectors()`. Nothing else
changes — scheduler, ingest, API, WebSocket, and the frontend are all source-agnostic. `fetch()`
builds its client with `app.http.make_client` (never `httpx.AsyncClient` directly); add the source
to `tests/test_http_wire.py`.

**Status contract:** set `NormalizedObservation.status` and nothing else. Ingest records it on the
entity as `latest_properties["status"]`, which change detection, `GET /entities` and the detail
panel read. Do not copy it into `properties`. The normalized status overrides any raw `status` key
in the payload, so if the upstream `status` means something else and must be kept, rename it.

**Status contract:** set `NormalizedObservation.status` and nothing else. Ingest records it on the
entity as `latest_properties["status"]`, which change detection, `GET /entities` and the detail
panel read. Do not copy it into `properties`. The normalized status overrides any raw `status` key
in the payload, so if the upstream `status` means something else and must be kept, rename it.

### The news feature (`app/news/`, ported from ChattNews)
Pipeline: **fetch → cluster → serve**, run as one APScheduler job every `news_refresh_minutes`
(default 15) and by `POST /api/v1/news/refresh`; the two paths are serialized by an asyncio lock in
`refresh.py`. Articles do **not** flow through collectors/ingest.

- `registry.py` — nine outlets + their feeds as **code-as-config**: synced into the DB at startup
  (upsert; feeds *and whole outlets* removed from the registry are deleted, articles cascading).
  Each feed has a section category and a `kind` (`rss` by default; `html` = a server-rendered
  listing page to scrape, used by the City of Chattanooga). A source registered with
  `use_feed_tags: False` declares its `<category>` tags meaningless. Specific sections are listed
  before the general news feed so the section fallback prefers the specific category.
- `classify.py` — **per-article content categorization**, first match wins: a mapped feed
  `<category>` tag → a keyword match on title + summary → the feed's section as last resort.
- `fetcher.py` — feedparser per `rss` feed (in a thread), BeautifulSoup for `html` feeds. Dedup is
  `UNIQUE(source_id, guid)`; the upsert recomputes and overwrites `category` on every fetch (other
  fields keep their first-seen values).
- `clustering.py` — after every fetch, articles in the story window (`news_story_window_days`,
  default 7) are re-clustered so articles about the **same event** share a `cluster_id` (= smallest
  member id). Titles are compared by IDF-weighted Jaccard/containment; vetoes block matches on
  disjoint numbers, unrelated summaries, and same-outlet recurring columns posted > 12 h apart.
  Articles are assigned in publish order to the best-matching story whose first article is ≤ 36 h
  older **and** that they match at least half of — a majority rule, not union-find, so one weak
  link can't chain stories. `assign_clusters()` is pure; `tests/test_news_clustering.py` gates
  precision/recall against a hand-labeled fixture. See the module docstring for details.
- `stories.py` — read model: one story per cluster with in-window members (headline from earliest,
  wordiest summary, majority-vote category with specific-beats-news ties, earliest image, one link
  per outlet).
- Tables: `news_sources` → `news_feeds` → `news_articles` (plain relational, migration `0002`;
  `image_url` added in `0007`).

**Feed gotchas (hard-won in ChattNews, don't regress):** requests must send the browser
`BROWSER_USER_AGENT` in `app/http.py` (TownNews/Local 3 429s unfamiliar UAs); Local 3 feeds are TownNews
search URLs (`c=local-news` / `c=local-sports*` — unfiltered mixes in national CNN wire); TFP's
`breakingnews` feed is valid-but-empty, `local/` is the working one, and TFP politics/life include
syndicated national content (known caveat); WDEF feeds live on `www.wdef.com` (apex 301s); a feed
erroring must never abort the cycle — per-feed status lands in `news_feeds.last_status`, surfaced
in the UI footer.

### The events feature (`app/events/`, ported from chattevents)
Pipeline: **fetch sources → ingest (dedup + tag + geocode) → serve**, run as one APScheduler job
every `events_refresh_minutes` (default 60) and by `POST /api/v1/events/refresh`; both paths share
an asyncio lock in `refresh.py` so all Nominatim traffic in a cycle uses one rate-limited geocoder.
Events are merged cross-source records, not entity state over time, so they do **not** flow through
collectors/ingest.

- `sources/` — config-driven `EventSource` subclasses: `CarCruiseFinderSource`, `ChattZooSource`
  (the Chattanooga Zoo's events page, scraped — the site publishes no machine endpoint at all),
  `CitySparkSource` (The Pulse's calendar via CitySpark's JSON API, `events_cityspark_*`
  settings), `MeetupSource`, `ICalSource` (one per configured calendar URL), and
  `TribeEventsSource` (The Events Calendar REST API on WordPress sites, one per
  `events_tribe_calendars` `Name=BaseURL` entry — by default the Chattanooga Public Library).
  Each yields normalized event records.
- A source supplies what it knows and the pipeline derives the rest: `RawEvent` may carry
  `latitude`/`longitude` and `tags`; ingest geocodes only events without coordinates and
  keyword-tags only events without supplied tags (supplied tag names are lowercased so they merge
  with the keyword vocabulary). CitySpark supplies both, so the largest source adds ~zero Nominatim
  traffic; `ChattZooSource` hardcodes its one venue's coordinates for the same reason.
- `ingest.py` — `run_sources()` fetches + upserts (dedup across sources), `tagging.py` assigns topic
  tags, and `geocoding.py` (`NominatimGeocoder`, rate-limited) resolves addresses to points;
  `retry_failed_geocodes()` reruns stale geocode misses under the same lock.
- Distance is done in PostGIS: the API casts `Event.location` to `geography` and filters/measures in
  meters from the shared center origin (`center_lat`/`center_lon` in `config.py`, Chattanooga by
  default — also used by the CitySpark/Meetup source defaults and the weather feature).
- Tables: `events` → `event_tags` / `event_links`, plus the `tags` vocabulary and the permanent
  `geocode_cache` (`app/events/models.py`). Startup purges any tag in `events_blocked_tags`
  (default `topics`, CitySpark's root tag).

**Events source gotchas (don't regress):** CitySpark's `DateStart`/`DateEnd` carry a `Z` suffix on
venue-local times — only `StartUTC`/`EndUTC` are real UTC; using the former shifts events by the
UTC offset and corrupts `canonical_key` dedup (events without `StartUTC` are skipped, never
defaulted). The same class of bug is why `CarCruiseFinderSource` parses only the listing page —
its detail pages carry wrong UTC offsets. `ChattZooSource` **must** fetch detail pages (the zoo's
listing page has no dates on it at all); this does not contradict the CarCruiseFinder rule, because
the zoo's detail pages carry no UTC offsets to be wrong. The zoo's dates are year-less free text
(`March 22 | 9:00 AM - 5:00 PM`) on pages that retain stale past occurrences, so each is resolved to
the nearest of the previous/current/next-year candidates and then dropped if already over — never
rolled forward, which would turn a leftover March entry into a fictional next-year event
(the rule is knowingly wrong past ~6 months out, and fails toward dropping, not inventing). One zoo
page lists several dates, so it fans out into one event each and `source_event_id` must carry the
occurrence date (`<slug>#<YYYY-MM-DD>`) or the occurrences collapse on the exact source-listing
dedup tier. CitySpark tag ids are rolled up to one level below their
root (`Performing Arts > Music > Live Music` → `music`) inside the source's pure parse function;
ingest never sees the hierarchy. A source erroring must never abort the refresh cycle
(per-source isolation in `run_sources()`).

### The weather feature (`app/weather/`)
Pipeline: **discover → fetch → cache → serve** — no DB tables, no migration. A `weather_refresh`
scheduler job runs every `weather_cache_minutes` and calls `get_current(force=True)` (bypassing the
TTL check) so the cache stays current without page loads, pinging `weather` on the live bus when
the payload changes; requests otherwise refresh lazily once the TTL expires.
`app/weather/nws.py` and `app/weather/airnow.py` hold pure payload-shaping functions
(offline-testable against `tests/fixtures/nws/` and `tests/fixtures/airnow/`);
`app/weather/service.py` fetches and caches; `app/api/weather.py`
serves `GET /api/v1/weather/current` (registration gated by `weather_enabled`). The location is
the shared `center_lat`/`center_lon` from `config.py`.

NWS is two-hop: `GET /points/{lat},{lon}` yields the gridpoint forecast URL + station list, which
are static for a fixed coordinate and resolved once per process (failed discovery is retried, not
cached). Steady state per cache expiry (`weather_cache_minutes`, default 10) is two calls —
forecast periods + latest station observation — plus a third, AirNow's current observation, when
`airnow_api_key` is set. AirNow fails independently (`aqi` null) and a last-good AQI is carried
forward for up to `airnow_stale_minutes` (default 120) past its observation time. Concurrent
requests coalesce behind an asyncio lock; a failed refresh serves the previous payload, a cold
failure 502s (the home strip degrades to a one-line notice without touching the other widgets).

**NWS gotchas (don't regress):** requests must send an identifying `User-Agent` (the global
`user_agent` setting, whose default ends in `LocalDash/0.1`); observations are °C / km/h and are converted to °F / mph; stations
sometimes report a **null temperature** — fall back to the next station, never render an empty
reading; the leading forecast period is **renamed through the day** ("Today" → "This Afternoon" →
"Tonight"), so period names are passed through verbatim and never hardcoded; station observations
can lag 20–60 min, so the response carries `observed_at` and the UI shows an "as of" time.

**Secrets in logs (don't regress):** AirNow only accepts its key as the `API_KEY` query
parameter (header auth is rejected), so the key is part of the request URL — which httpx echoes
in its INFO request log and in every `HTTPStatusError` message/traceback. `app/redaction.py`
handles this globally: `install()` (called in `main.py`) wraps the LogRecord factory so every
record's message, args, and traceback are scrubbed of secret-looking query params and the
literal values of the credential settings (`SECRET_SETTINGS`) before any handler sees them; use
`redact()` on exception text that is persisted or returned (`sources.last_error`,
`news_feeds.last_status`). Add new credential settings to `SECRET_SETTINGS`.

### Backend code organisation
The backend (`app/`) is one application. Its packages (`app/news/`, `app/events/`,
`app/weather/`, `app/collectors/`) and its top-level modules group code by feature to make it
easier to find. They are not boundaries: any backend module may import from any other.

Before writing a helper, constant or mechanism, look for an existing one anywhere in `app/`
and reuse it. If it lives somewhere awkward for the new caller, promote it to a shared
module (move it, then import it from both places) instead of copying it. Two copies of the
same logic drift apart.

Feature separation still holds in three places, and none of them is about backend imports:
- **Data flow.** News, events and weather do not flow through collectors/ingest; each has
  its own pipeline and tables (weather has none).
- **The API.** Each feature owns `/api/v1/<feature>/` and one router module in `app/api/`.
- **The frontend.** Its import rules (above) apply to `frontend/src/` only.

**Import cycles.** Shared code should sit below the code that uses it. Entry and orchestration
modules (`main.py`, `scheduler.py`, `app/api/`) import feature code; feature code should not
import them. When two modules need each other's code, move the shared part into a module both
can import, rather than adding a function-local import. This is advice for fixing a cycle,
not a list of forbidden imports.

### API / frontend conventions
- The API is **versioned and feature-namespaced**: every feature owns a namespace under
  `/api/v1/<feature>/` (`timeseries`, `news`, `events`, `weather`), and feature-agnostic app-shell
  endpoints (`/api/v1/config` and the `/api/v1/ws` live-update WebSocket) sit directly under
  `/api/v1`. Each feature is one `APIRouter` module in `app/api/` (`timeseries.py`, `news.py`,
  `events.py`, `weather.py`, `root.py` for app-shell), composed in
  `main.py` — adding a feature is a new router module + one `include_router` line (the news router
  is always mounted, `news_enabled` only gates its scheduler job; the weather router is mounted only
  when `weather_enabled`). `main.py` mounts `static/` at `/` last so `/api` always wins (with an SPA
  fallback: extension-less non-`/api` misses serve `index.html`).
- All geographic responses are **GeoJSON FeatureCollections** (`geojson.py`). `bbox` params are
  `minLon,minLat,maxLon,maxLat`.
- Timeseries routes are resource-shaped: `GET /api/v1/timeseries/entities` (filters: `active`
  [default true], `source`, `category`, `bbox`, `closed_within` minutes), `/entities/{id}` (snapshot
  only), `/entities/{id}/track` (history), `/observations` (`limit` 1–50000, default 5000),
  `/sources`, and `POST /sources/{key}/refresh` (serialized with the scheduled tick by a per-source
  lock). Live diffs arrive on the global `/api/v1/ws` bus, not a timeseries route.
- News routes: `GET /api/v1/news/stories?hours=N&limit=M` (returns the category slug→label map +
  one story per cluster; `limit` optional, newest first), `GET /api/v1/news/sources` (per-feed
  health for the footer), `POST /api/v1/news/refresh`.
- Events routes (JSON, not GeoJSON): `GET /api/v1/events/items` (filters: `topic`, `max_miles` +
  `lat`/`lon` origin, `upcoming` [default true], `search`, `limit`; each item carries
  `distance_miles`), `GET /api/v1/events/tags`, `POST /api/v1/events/refresh`.
- Weather route: `GET /api/v1/weather/current` (current station observation, the leading NWS
  forecast periods, and `aqi` — null without an AirNow key; served from the in-process cache, 502
  only when NWS is unreachable with a cold cache).
- The frontend (`frontend/`, Svelte + TS, built into `static/`) lays out its source by the same
  feature namespaces (its import rules are frontend-only):
  `src/features/home/` is the `/` widget digest (news, weather, outages, today's events);
  `src/features/timeseries/` loads `/api/v1/timeseries/entities` and applies bus diffs into a runes
  store; `src/features/news/` and `src/features/events/` load into their own runes stores and
  refetch when their bus ping arrives (no polling timers); `src/lib/` holds the feature-agnostic
  shell code, including the path router and the singleton live-update bus (`live.svelte.ts`, one
  WebSocket to `/api/v1/ws` shared by every feature).

## Config
All settings come from env / `.env` via `config.py` (pydantic-settings) — DB URL, the hc911
token/origin, tile layer, poll intervals, the news knobs (`news_enabled`,
`news_refresh_minutes`, `news_story_window_days`; the outlet/feed list itself is code in
`app/news/registry.py`), the events knobs (`events_*`: refresh interval, iCal feeds, tribe
calendars, CitySpark, Meetup token, geocoder throttle and retry, ingest radius, tag blocklist), the
weather knobs (`weather_enabled`, `weather_cache_minutes`, `airnow_api_key`,
`airnow_stale_minutes`), and the shared center coordinate (`center_lat`/`center_lon`, exposed as
the `settings.center` tuple) used
by the events distance origin, the CitySpark/Meetup source defaults, and the weather location.
There is no `.env` by default; the code runs on the defaults in
`config.py`. Inside Docker the app reaches Postgres at host `db`; locally at `localhost`.
