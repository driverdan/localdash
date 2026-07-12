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

## Git workflow (required)

All changes must use git version control and follow a standard branch + pull request process:

1. **Never commit directly to `main`.** Start every change on a new branch with a unique, semantic
   name describing the change (e.g. `add-aprs-collector`, `fix-closure-sweep-race`).
2. When the change is complete, **commit** it to that branch.
3. **Push** the branch to GitHub.
4. **Open a pull request** for the change.

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
