# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

LocalDash is a local-data dashboard with three features:

- **Timeseries** (`/map`): stores, serves, and views **time-series geolocation data** — active 911
  incidents for Hamilton County TN, TDOT SmartWay roadway events, EPB outages, and TN American Water
  advisories. The geo stack is deliberately source-agnostic so APRS / weather / other geo feeds can
  be added without schema changes.
- **News** (`/`, the homepage): an RSS aggregator for Chattanooga outlets that clusters articles
  covering the same story across outlets (ported from the standalone ChattNews app). Not a geo
  source — it is a sibling feature beside the timeseries pipeline, not a collector.
- **Events** (`/events`): aggregates, de-duplicates, tags, and geocodes local happenings (car
  cruises, Meetup groups, configurable iCal calendars; ported from the `chattevents` PoC). Also a
  sibling feature — events are merged cross-source records, not entity-state-over-time, so they do
  not flow through collectors/ingest.

## Tech stack & why

**Data store — Postgres + PostGIS + TimescaleDB** (one image: `timescale/timescaledb-ha:pg16`).
- *PostgreSQL*: relational base with strong JSONB support, which the schema leans on for
  source-specific fields (no per-source migrations).
- *PostGIS*: real geospatial types + indexes; the API does bbox / `ST_Intersects` / `ST_X` queries
  rather than filtering points in Python.
- *TimescaleDB*: turns `observations` into a hypertable partitioned on `observed_at`, giving the
  time-series side scalable inserts/scans and easy retention policies as history grows. The HA image
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
the FastAPI event loop — one job per geo collector plus one news-refresh job. Deliberately avoids a
separate worker + broker (Celery/Redis): at this scale a background task is simpler and has no extra
moving parts.

**HTTP client — httpx.** Async client for fetching upstream sources, matching the async stack (and the
same library FastAPI's TestClient builds on).

**RSS parsing — feedparser.** Synchronous, so the news fetcher runs it in `asyncio.to_thread`;
kept over an httpx rewrite because its redirect/encoding/entity handling is what the ported
ChattNews behavior was tuned against.

**Config / validation — Pydantic v2 + pydantic-settings.** Typed settings loaded from env/`.env`, and
`NormalizedObservation` is a Pydantic model so collector output is validated at the boundary.

**Python dependency locking — uv (`uv.lock`).** The project stays plain PEP 621: uv owns no
metadata in `pyproject.toml`, so `pip install -e ".[dev]"` keeps working and uv is removable by
deleting one file. It is used for the one thing pip cannot do here — produce a **universal**
lock. `uv.lock` carries environment markers covering the whole `requires-python = ">=3.11"` range
and Linux/macOS/Windows, which matters because this repo spans interpreters: Docker and CI run
3.12 while local venvs run 3.13. The standard `pylock.toml` was the obvious alternative and was
rejected on three counts: `pip lock` is experimental and self-describes as removable without
warning; its output resolves against *one* interpreter (a lock built on 3.13 pins `cp313` wheels
and hard-fails on 3.12, and vice versa), so no single file could serve both; and Dependabot cannot
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

The frontend mirrors the API's feature-namespace convention: each feature owns
`frontend/src/features/<feature>/` (`news` on `/`, `timeseries` on `/map` — the latter owns the
Leaflet map), composed per-route by `App.svelte`; feature-agnostic shell code lives in
`frontend/src/lib/`. Routing is a **tiny hand-rolled path router** (`lib/router.svelte.ts`: reactive
path + `pushState` + `popstate` — two routes don't justify a dependency), backed by an SPA fallback
in `main.py`'s static mount (extension-less non-`/api` 404s serve `index.html` so `/map` deep-links).
**Import rules:** features import from `lib/` and themselves, never from another feature; the shell
imports only each feature's `index.ts`; `lib/` imports from no feature. Adding a frontend feature =
new folder + one route entry in `App.svelte` — the counterpart of "new router + one `include_router`
line".

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
News feed at http://localhost:8000/, map dashboard at http://localhost:8000/map, events at
http://localhost:8000/events.

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
uv lock --upgrade-package fastapi  # bump one dep to the newest its ~= range allows
uv lock --upgrade                  # re-resolve everything within the declared ranges
uv lock                            # after hand-editing pyproject.toml — never leave the lock stale
```
Direct deps are pinned with **tilde ranges** (`~=X.Y.Z` = that patch series only), so minors and
majors are opted into by editing `pyproject.toml`, never picked up by an install. Widening a range
is the deliberate act; `uv lock` then records the exact transitive set. **Any change to
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
Most tests are pure/offline. The DB-backed tests (`tests/test_ingest.py::test_ingest_full_lifecycle`,
`tests/test_api_timeseries.py`, and `tests/test_news_db.py`, via the `db_session` / `news_db_session`
fixtures in `conftest.py`) **auto-skip** unless `DATABASE_URL` points at a reachable Postgres —
bring up `docker compose up -d db` (and `alembic upgrade head` for the news tables) to make them run.

**CI:** `.github/workflows/tests.yml` runs on every PR and on pushes to `main`, in two jobs whose
checks are required by the default-branch ruleset — a failure blocks the merge button.

- **`pytest`** — the full suite. CI stands up the same `timescale/timescaledb-ha:pg16` image as a
  service container and runs `alembic upgrade head` first, so the DB-backed tests actually execute
  rather than auto-skipping. That migrate step doubles as the guard: if the DB were unreachable it
  fails loudly instead of letting the suite skip its way to green. The job also `mkdir -p static`
  first — `static/` is a gitignored build artifact and `main.py` mounts it at import time, so a fresh
  checkout can't even import the app without it. Installs are `uv sync --locked`, which makes the
  job double as the lockfile gate: a `pyproject.toml` dependency edit without a matching `uv lock`
  fails here instead of merging a stale lock.
- **`frontend`** — `npm run check` + `npm run build`. There is **no JS test suite** (no runner, no
  `*.test.ts`), so these stand in as the frontend gate; they're what catches a bad npm bump, which
  `pytest` never sees. If a JS test runner is ever added, wire `npm test` into this job.

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
rather than an enforcement boundary — CI covers `pytest` only. A `pre-commit run --all-files` job
(and `npm run check`) alongside it is deferred to a later change.

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
     `master_incident_id`),
   - **append an `observation` only when state changed** (status moved or position moved > epsilon) —
     this is what avoids one duplicate row per poll, and is the core of the time-series,
   - **closure sweep**: entities that were active but are absent from this payload are flipped
     `is_active=false` with a final `Closed` observation.
   - returns a `Diff` (`new`/`updated`/`closed`).
4. The scheduler broadcasts that `Diff` over the **`/api/v1/timeseries/ws` WebSocket** (`ws.py`); the
   frontend applies it incrementally.

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
  `latest_properties`. Unique on `(source_key, external_id)`.
- `observations` — the hypertable; PostGIS `geom` point + JSONB `properties`. Source-specific fields
  live in JSONB so new sources need no migration.

### Adding a data source
Write a `BaseCollector` subclass in `app/collectors/<name>.py` (implement async `fetch()` and pure
`normalize()`), then register it in `app/collectors/__init__.py`'s `build_collectors()`. Nothing else
changes — scheduler, ingest, API, WebSocket, and the frontend are all source-agnostic.

### The news feature (`app/news/`, ported from ChattNews)
Pipeline: **fetch → cluster → serve**, run as one APScheduler job every `news_refresh_minutes`
(default 15) and by `POST /api/v1/news/refresh`; the two paths are serialized by an asyncio lock in
`refresh.py`. Articles do **not** flow through collectors/ingest.

- `registry.py` — outlets + per-section feeds as **code-as-config**: synced into the DB at startup
  (upsert; feeds removed from the registry are deleted). The sites' feeds carry no `<category>`
  tags, so *which section feed* an article appeared in supplies its category; specific sections are
  listed before the general news feed so overlapping articles keep the specific category.
- `fetcher.py` — feedparser per feed (in a thread). Dedup is `UNIQUE(source_id, guid)` with an
  upsert that only upgrades category `'news'` → specific, never the reverse.
- `clustering.py` — after every fetch, articles in the story window (7 days) are pairwise-compared
  by title (token Jaccard/containment + SequenceMatcher + a distinctive-shared-tokens rule that
  applies **only across outlets** — within one outlet it falsely merges formulaic series headlines)
  and merged with union-find; `cluster_id` = smallest member article id. `assign_clusters()` is
  pure; tests cover it offline.
- `stories.py` — read model: one story per cluster (headline from earliest, wordiest summary,
  majority-vote category with specific-beats-news ties, one link per outlet).
- Tables: `news_sources` → `news_feeds` → `news_articles` (plain relational, migration `0002`).

**Feed gotchas (hard-won in ChattNews, don't regress):** requests must send the browser
`USER_AGENT` in `registry.py` (TownNews/Local 3 429s unfamiliar UAs); Local 3 feeds are TownNews
search URLs (`c=local-news` / `c=local-sports*` — unfiltered mixes in national CNN wire); TFP's
`breakingnews` feed is valid-but-empty, `local/` is the working one, and TFP politics/life include
syndicated national content (known caveat); WDEF feeds live on `www.wdef.com` (apex 301s); a feed
erroring must never abort the cycle — per-feed status lands in `news_feeds.last_status`, surfaced
in the UI footer.

### The events feature (`app/events/`, ported from chattevents)
Pipeline: **fetch sources → ingest (dedup + tag + geocode) → serve**, run as one APScheduler job and
by `POST /api/v1/events/refresh`; both paths share an asyncio lock in `refresh.py` so all Nominatim
traffic in a cycle uses one rate-limited geocoder. Events are merged cross-source records, not entity
state over time, so they do **not** flow through collectors/ingest.

- `sources/` — config-driven `EventSource` subclasses: `CarCruiseFinderSource`, `MeetupSource`, and
  `ICalSource` (one per configured calendar URL). Each yields normalized event records.
- `ingest.py` — `run_sources()` fetches + upserts (dedup across sources), `tagging.py` assigns topic
  tags, and `geocoding.py` (`NominatimGeocoder`, rate-limited) resolves addresses to points;
  `retry_failed_geocodes()` reruns stale geocode misses under the same lock.
- Distance is done in PostGIS: the API casts `Event.location` to `geography` and filters/measures in
  meters from a Chattanooga origin (`CHATTANOOGA_CENTER`).
- Tables: `events` → `event_tags` / `event_links` (`app/events/models.py`).

### API / frontend conventions
- The API is **versioned and feature-namespaced**: every feature owns a namespace under
  `/api/v1/<feature>/` (`timeseries`, `news`, `events`), and feature-agnostic app-shell endpoints
  (`/api/v1/config`) sit directly under `/api/v1`. Each feature is one `APIRouter` module in
  `app/api/` (`timeseries.py`, `news.py`, `events.py`, `root.py` for app-shell), composed in
  `main.py` — adding a feature is a new router module + one `include_router` line. `main.py` mounts
  `static/` at `/` last so `/api` always wins (with an SPA fallback: extension-less non-`/api` misses
  serve `index.html`).
- All geographic responses are **GeoJSON FeatureCollections** (`geojson.py`). `bbox` params are
  `minLon,minLat,maxLon,maxLat`.
- Timeseries routes are resource-shaped: `GET /api/v1/timeseries/entities` (filters: `active`
  [default true], `source`, `category`, `bbox`, `closed_within` minutes), `/entities/{id}` (snapshot
  only), `/entities/{id}/track` (history), `/observations`, `/sources`, `POST /sources/{key}/refresh`,
  and the `/ws` WebSocket.
- News routes: `GET /api/v1/news/stories?hours=N` (returns the category slug→label map + one story
  per cluster), `GET /api/v1/news/sources` (per-feed health for the footer), `POST
  /api/v1/news/refresh`.
- Events routes (JSON, not GeoJSON): `GET /api/v1/events/items` (filters: `topic`, `max_miles` +
  `lat`/`lon` origin, `upcoming` [default true], `search`, `limit`; each item carries
  `distance_miles`), `GET /api/v1/events/tags`, `POST /api/v1/events/refresh`.
- The frontend (`frontend/`, Svelte + TS, built into `static/`) mirrors the namespace convention:
  `src/features/timeseries/` loads `/api/v1/timeseries/entities`, then opens the WebSocket and
  applies diffs into a runes store; `src/features/news/` loads stories/sources into its own runes
  store (5-minute auto-reload, no WebSocket); `src/features/events/` loads `/api/v1/events/items`
  into its own store; `src/lib/` holds the feature-agnostic shell code (including the path router).

## Config
All settings come from env / `.env` via `config.py` (pydantic-settings) — DB URL, the hc911
token/origin, tile layer, poll intervals, retention, and the news knobs (`news_enabled`,
`news_refresh_minutes`, `news_story_window_days`; the outlet/feed list itself is code in
`app/news/registry.py`). There is no `.env` by default; the code runs on the defaults in
`config.py`. Inside Docker the app reaches Postgres at host `db`; locally at `localhost`.
