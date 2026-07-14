# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

LocalDash is a local-data dashboard with two features:

- **Timeseries** (`/map`): stores, serves, and views **time-series geolocation data** — active 911
  incidents for Hamilton County TN, TDOT SmartWay roadway events, and EPB outages. The geo stack is
  deliberately source-agnostic so APRS / weather / other geo feeds can be added without schema changes.
- **News** (`/`, the homepage): an RSS aggregator for Chattanooga outlets that clusters articles
  covering the same story across outlets (ported from the standalone ChattNews app). Not a geo
  source — it is a sibling feature beside the timeseries pipeline, not a collector.

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
News feed at http://localhost:8000/, map dashboard at http://localhost:8000/map.

**Local dev (Dockerized DB, app from venv with --reload):**
```bash
docker compose up -d db
source .venv/bin/activate         # venv already exists with deps installed
pip install -e ".[dev]"           # if recreating the env
cp .env.example .env              # DATABASE_URL -> localhost:5432
alembic upgrade head
uvicorn app.main:app --reload
```

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

**Linting & formatting (pre-commit):** a git pre-commit hook auto-fixes and lints **staged**
code — `ruff check --fix` + `ruff format` for Python, `prettier` for `frontend/`. Enable it once
per clone (hooks are not installed automatically):
```bash
pip install -e ".[dev]"           # installs pre-commit + ruff into the venv
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
`git commit --no-verify` and there is no CI backstop yet, so it is a convenience, not an
enforcement boundary; a `pre-commit run --all-files` CI job is deferred to a later change.

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

### API / frontend conventions
- The API is **versioned and feature-namespaced**: every feature owns a namespace under
  `/api/v1/<feature>/` (`timeseries`, `news`), and feature-agnostic app-shell endpoints
  (`/api/v1/config`) sit directly under `/api/v1`. Each feature is one `APIRouter` module in
  `app/api/` (`timeseries.py`, `news.py`, `root.py` for app-shell), composed in `main.py` — adding a
  feature is a new router module + one `include_router` line. `main.py` mounts `static/` at `/` last
  so `/api` always wins (with an SPA fallback: extension-less non-`/api` misses serve `index.html`).
- All geographic responses are **GeoJSON FeatureCollections** (`geojson.py`). `bbox` params are
  `minLon,minLat,maxLon,maxLat`.
- Timeseries routes are resource-shaped: `GET /api/v1/timeseries/entities` (filters: `active`
  [default true], `source`, `category`, `bbox`, `closed_within` minutes), `/entities/{id}` (snapshot
  only), `/entities/{id}/track` (history), `/observations`, `/sources`, `POST /sources/{key}/refresh`,
  and the `/ws` WebSocket.
- News routes: `GET /api/v1/news/stories?hours=N` (returns the category slug→label map + one story
  per cluster), `GET /api/v1/news/sources` (per-feed health for the footer), `POST
  /api/v1/news/refresh`.
- The frontend (`frontend/`, Svelte + TS, built into `static/`) mirrors the namespace convention:
  `src/features/timeseries/` loads `/api/v1/timeseries/entities`, then opens the WebSocket and
  applies diffs into a runes store; `src/features/news/` loads stories/sources into its own runes
  store (5-minute auto-reload, no WebSocket); `src/lib/` holds the feature-agnostic shell code
  (including the path router).

## Config
All settings come from env / `.env` via `config.py` (pydantic-settings) — DB URL, the hc911
token/origin, tile layer, poll intervals, retention, and the news knobs (`news_enabled`,
`news_refresh_minutes`, `news_story_window_days`; the outlet/feed list itself is code in
`app/news/registry.py`). There is no `.env` by default; the code runs on the defaults in
`config.py`. Inside Docker the app reaches Postgres at host `db`; locally at `localhost`.
