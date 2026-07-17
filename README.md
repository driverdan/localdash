# LocalDash

A self-hosted **local-data dashboard** for the Chattanooga / Hamilton County, TN
area. It bundles three sibling features behind one FastAPI app and one Svelte SPA:

| Feature | Route | What it does |
| --- | --- | --- |
| **News** | `/` | RSS aggregator that clusters the same story across local outlets |
| **Map** (timeseries) | `/map` | Live + historical **time-series geolocation** on a Leaflet map |
| **Events** | `/events` | Aggregated, de-duplicated area events (car cruises, meetups, civic calendars) |

The three features share a database, a scheduler, and the app shell, but they are
independent pipelines — News and Events do **not** flow through the geo
collector/ingest path. Open <http://localhost:8000/> for News and
<http://localhost:8000/map> for the map after starting the stack (below).

## Map — time-series geolocation

Store, serve, and view time-series geolocation data. The design is
**source-agnostic**: each upstream feed is a **snapshot** of what's currently
active, and LocalDash builds the **time-series** itself. A background scheduler
polls each source, tracks each thing by a stable id, appends an observation row
whenever its status or position changes, and closes it when it drops out of the
feed. Adding a feed is one small collector class — no schema changes.

```
collector.fetch() ── raw payload
        │
   normalize() ──── list[NormalizedObservation]   (source-agnostic)
        │
   ingest() ─────── upsert entity · append observation on change · close on absence
        │
   ┌────┴─────┐
 REST API   WebSocket diffs ──► Svelte + Leaflet map (map + filters + live table)
```

### Built-in geo sources

Four collectors ship out of the box. Each has a reverse-engineered API reference
under [`docs/`](docs/); the map's **Source** selector switches between them.

| Source | `source_key` | What | Docs |
| --- | --- | --- | --- |
| Hamilton County TN 911 | `hc911` | Active 911 incidents | [`docs/hc911-api.md`](docs/hc911-api.md) |
| TDOT SmartWay | `tdot` | Roadway events (incidents / construction / special events / severe-impact) across TN | [`docs/tdot-smartway-api.md`](docs/tdot-smartway-api.md) |
| EPB Outages | `epb` | Chattanooga electric + fiber outages | [`docs/epb-outage-api.md`](docs/epb-outage-api.md) |
| TN American Water Advisories | `tnaw` | Water advisory affected-area polygons across TN | [`docs/tnaw-advisory-api.md`](docs/tnaw-advisory-api.md) |

### Data model (Postgres + PostGIS + TimescaleDB)

- **`sources`** — one row per registered source + last-run telemetry.
- **`entities`** — one tracked thing per source (latest snapshot, `is_active`,
  `last_geom`, `latest_properties`). Unique on `(source_key, external_id)`.
- **`observations`** — the time-series, a TimescaleDB **hypertable** on
  `observed_at`, with a PostGIS `geom` (point *or* polygon). Source-specific fields
  live in JSONB, so new sources need no migration.

## News — clustered local headlines

An RSS aggregator for Chattanooga outlets (ported from the standalone **ChattNews**
app), served at `/`. It fetches each outlet's section feeds on a schedule, then
clusters articles that cover the same story **across outlets** so one story shows
one headline with a link per outlet.

Pipeline: **fetch → cluster → serve**, run as one scheduler job (every
`NEWS_REFRESH_MINUTES`, default 15) and on demand via `POST /api/v1/news/refresh`.
The outlet/feed list is code-as-config in `app/news/registry.py`; stories live in
their own relational tables (`news_sources` → `news_feeds` → `news_articles`),
separate from the geo pipeline.

## Events — aggregated area events

Aggregates, de-duplicates, tags, and geocodes local happenings (ported from the
`chattevents` PoC), served at `/events`. Sources include **CarCruiseFinder**,
**Meetup**, The Pulse's **CitySpark** calendar, configurable **iCal** calendars,
and configurable **The Events Calendar (tribe)** WordPress calendars (by default
the Chattanooga Public Library's).

Pipeline: **fetch sources → ingest (dedup + tag + geocode) → serve**, run as one
scheduler job and on demand via `POST /api/v1/events/refresh`. Geocoding uses a
rate-limited Nominatim client; the API filters by distance from a Chattanooga
origin in PostGIS (geography, so distances are real meters). Events are merged
cross-source records, not entity-state-over-time, so they do **not** use the
collector/ingest path.

## Quick start (Docker — full stack)

Brings up Postgres (PostGIS + TimescaleDB) **and** the app. The app container waits
for the DB to be healthy, runs `alembic upgrade head`, then serves the API +
dashboard and starts the poll scheduler.

```bash
docker compose up --build
```

Then open the **News** homepage at <http://localhost:8000/> and the **map** at
<http://localhost:8000/map> (Events at <http://localhost:8000/events>).

> If you hit `permission denied … /var/run/docker.sock`, add yourself to the
> `docker` group once: `sudo usermod -aG docker $USER`, then start a new shell (or
> `newgrp docker`) and re-run.

## Quick start (local app, Dockerized DB)

Run just Postgres in Docker and the app from your venv (nice for `--reload` dev):

Needs [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`) — it
installs the exact dependency versions pinned in `uv.lock`, the same ones CI and the Docker image
use. The full-Docker quick start above needs nothing but Docker.

```bash
# 1. Database only
docker compose up -d db

# 2. Python env + deps (uv creates .venv and installs the exact versions in uv.lock)
uv sync --extra dev
source .venv/bin/activate

# 3. Config + migrations
cp .env.example .env          # DATABASE_URL points at localhost:5432
alembic upgrade head

# 4. Run
uvicorn app.main:app --reload

# 5. Frontend (Svelte + Vite; source in frontend/, builds into static/)
cd frontend && npm install
npm run build        # one-off build served by uvicorn at :8000
npm run dev          # or: hot-reload dev server at :5173, proxies /api to :8000
```

## Expose publicly with a Cloudflare named tunnel (optional)

The `cloudflared` compose service (behind the `tunnel` profile) publishes the app
over HTTPS without opening any inbound ports — it dials **out** to Cloudflare, so it
works behind NAT/CGNAT and needs no port forwarding or static IP.

One-time setup:

1. Add a domain to Cloudflare (move its nameservers to Cloudflare — free plan).
2. In the **Zero Trust** dashboard → **Networks → Tunnels**, create a tunnel.
   Under **Public Hostname**, route your chosen hostname to the service
   `http://app:8000` (the app is reachable at `app` on the compose network).
3. Copy the tunnel's connector token into `.env` as `CLOUDFLARE_TUNNEL_TOKEN`.

Then start the stack with the tunnel:

```bash
docker compose --profile tunnel up -d --build
```

Your hostname now serves the dashboard. Notes:

- Only `app:8000` is exposed; Postgres stays private to the compose network.
- The app ships **no authentication** — anyone with the URL can read the dashboard
  and API. Gate it with Cloudflare Access (free) if that matters.

## API

Every feature owns a namespace under `/api/v1/<feature>/`; feature-agnostic
app-shell routes sit directly under `/api/v1`. Geographic responses are GeoJSON
FeatureCollections; `bbox` is `minLon,minLat,maxLon,maxLat` and times are ISO-8601.

**App shell**

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/v1/config` | Frontend bootstrap (map tile layer + attribution) |
| WS | `/api/v1/ws` | Global live-update bus: `{topic: "timeseries", type: "diff"}` diffs each poll cycle, plus `{topic: "news"\|"events"\|"weather", type: "updated"}` refetch pings |

**Timeseries** — prefix `/api/v1/timeseries`

| Method | Path | Description |
| --- | --- | --- |
| GET | `/sources` | Registered sources + last-run telemetry |
| GET | `/entities?active=&source=&category=&bbox=&closed_within=` | Tracked entities as GeoJSON. `active` (default true) returns live entities; `closed_within=N` (minutes) also includes recently-closed ones; `active=false` returns only inactive. Each feature's `properties.active` flags live vs. closed |
| GET | `/entities/{id}` | Entity snapshot (no track) |
| GET | `/entities/{id}/track` | Full observation history, oldest first |
| GET | `/observations?source=&category=&bbox=&start=&end=&limit=` | Historical observations (GeoJSON) |
| POST | `/sources/{key}/refresh` | Trigger one collection cycle now |

**News** — prefix `/api/v1/news`

| Method | Path | Description |
| --- | --- | --- |
| GET | `/stories?hours=N` | Clustered stories in the window + category slug→label map |
| GET | `/sources` | Per-feed health (for the sources footer) |
| POST | `/refresh` | Fetch all feeds and recluster now |

**Events** — prefix `/api/v1/events`

| Method | Path | Description |
| --- | --- | --- |
| GET | `/items?topic=&max_miles=&lat=&lon=&upcoming=&search=&limit=` | De-duplicated events (JSON), with distance from the origin (Chattanooga unless `lat`/`lon` given) |
| GET | `/tags` | All topic tags |
| POST | `/refresh` | Fetch all sources and upsert now |

## Adding a geo data source

1. Create `app/collectors/<name>.py` with a `BaseCollector` subclass:
   ```python
   class WeatherCollector(BaseCollector):
       source_key = "weather"
       name = "NWS Weather"
       poll_interval = 300

       async def fetch(self): ...                # network I/O
       def normalize(self, raw) -> list[NormalizedObservation]: ...
   ```
   Map each record to a `NormalizedObservation` (`external_id`, `category`, `lat`,
   `lon`, `status`, `label`, `properties`).
2. Register it in `app/collectors/__init__.py` `build_collectors()`.

That's it — the scheduler, ingestion, REST API, WebSocket, and map are all
source-agnostic and pick it up automatically. Moving objects (APRS), evolving
incidents (911), point readings (weather), and affected-area polygons (water
advisories) all fit the same model.

> News outlets and Events sources are **not** geo collectors — add a news feed in
> `app/news/registry.py` or an events source under `app/events/sources/`.

## Tests

```bash
pytest
```

Most tests are pure/offline (`normalize`, the change-detection rule, and news
clustering run against saved fixtures). DB-backed tests auto-skip unless
`DATABASE_URL` points at a reachable Postgres — bring up `docker compose up -d db`
(and `alembic upgrade head`) to run them.

## Linting & formatting

A [pre-commit](https://pre-commit.com/) hook auto-fixes and lints **staged** code —
`ruff` for Python, `prettier` for the frontend. Enable it once per clone (hooks are
not installed automatically):

```bash
uv sync --extra dev          # pre-commit + ruff
cd frontend && npm install   # prettier + prettier-plugin-svelte
pre-commit install           # from the repo root
```

If a hook reformats a file the commit **aborts** so you can review the change, then
re-stage and commit again — fixes are never committed unseen. Run on the whole tree
with `pre-commit run --all-files`, or format the frontend directly via `npm run format`.
The hook is bypassable with `git commit --no-verify`, and there is no CI check yet, so
treat it as a convenience rather than a hard gate.

## Git workflow

All changes use git version control and follow a standard branch + pull request process:

1. **Never commit directly to `main`.** Start every change on a new branch with a unique, semantic
   name describing the change (e.g. `add-aprs-collector`, `fix-closure-sweep-race`).
2. When the change is complete, **commit** it to that branch.
3. **Push** the branch to GitHub.
4. **Open a pull request** for the change.

Larger changes use the **OpenSpec** workflow (`openspec/`) and land as three
sequential PRs (propose → implement → archive); see [`AGENTS.md`](AGENTS.md).

## Notes

- **Config / secrets** (`X-Frontend-Auth`, origin, DB URL, tile layer, poll
  intervals, news/events knobs) come from `.env` via pydantic-settings — nothing is
  hardcoded. The app runs on the defaults in `app/config.py` with no `.env` at all.
- **Be a good upstream citizen**: a descriptive `USER_AGENT` is sent, poll intervals
  are never set below a source site's own cadence, and the Events geocoder is
  rate-limited.
- **Retention**: set `RETENTION_DAYS` and add a TimescaleDB
  `add_retention_policy('observations', INTERVAL 'N days')` to auto-drop old
  history (left at keep-forever by default).

## License

LocalDash is licensed under the **GNU Affero General Public License v3.0 or later**
(AGPL-3.0-or-later). See [LICENSE](LICENSE) for the full text.

Because this is an AGPL-licensed network application, if you run a modified version
of LocalDash and let users interact with it over a network, you must also offer those
users the corresponding source code of your modified version.
