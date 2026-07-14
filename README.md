# LocalDash

Store, serve, and view **time-series geolocation data** in a web dashboard. Built-in
sources are **active 911 incidents** for Hamilton County, TN and **TDOT SmartWay**
roadway events (incidents / construction / special events / severe-impact across
Tennessee). The design is source-agnostic so APRS, weather, and other
real-time/historical geo feeds can be added by writing one small collector class.

## How it works

```
collector.fetch() ── raw payload
        │
   normalize() ──── list[NormalizedObservation]   (source-agnostic)
        │
   ingest() ─────── upsert entity · append observation on change · close on absence
        │
   ┌────┴─────┐
 REST API   WebSocket diffs ──► Svelte + Leaflet dashboard (map + filters + live table)
```

The upstream 911 endpoint returns only a **snapshot** of currently-active calls.
LocalDash builds the **time-series** itself: a background scheduler polls every
60s, tracks each incident by `master_incident_id`, appends an observation row
whenever its status or position changes, and marks it closed when it drops out of
the feed.

Each upstream feed is a snapshot too, so every source is built the same way. The
feeds are documented in [`docs/hc911-api.md`](docs/hc911-api.md) and
[`docs/tdot-smartway-api.md`](docs/tdot-smartway-api.md) (endpoints, auth, field
reference, and behavioral caveats). The frontend has a **Source** selector to switch
between them.

### Data model (Postgres + PostGIS + TimescaleDB)

- **`sources`** — one row per registered source + last-run telemetry.
- **`entities`** — one tracked thing per source (latest snapshot, `is_active`,
  `last_geom`, `latest_properties`). Unique on `(source_key, external_id)`.
- **`observations`** — the time-series, a TimescaleDB **hypertable** on
  `observed_at`, with a PostGIS `geom` point. Source-specific fields live in JSONB.

## Quick start (Docker — full stack)

Brings up Postgres (PostGIS + TimescaleDB) **and** the app. The app container waits
for the DB to be healthy, runs `alembic upgrade head`, then serves the API +
dashboard and starts the poll scheduler.

```bash
docker compose up --build
```

Open <http://localhost:8000/> for the dashboard.

> If you hit `permission denied … /var/run/docker.sock`, add yourself to the
> `docker` group once: `sudo usermod -aG docker $USER`, then start a new shell (or
> `newgrp docker`) and re-run.

## Quick start (local app, Dockerized DB)

Run just Postgres in Docker and the app from your venv (nice for `--reload` dev):

```bash
# 1. Database only
docker compose up -d db

# 2. Python env + deps
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

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

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/config` | Frontend bootstrap (map tiles) |
| GET | `/api/sources` | Registered sources + last-run status |
| GET | `/api/active?source=&category=&bbox=&include_closed=&closed_within_minutes=` | Active entities as GeoJSON. With `include_closed=true`, also returns entities closed within `closed_within_minutes` (default 60); each feature's `properties.active` flags live vs. closed |
| GET | `/api/entities/{id}` | Entity snapshot + full observation track |
| GET | `/api/observations?source=&start=&end=&bbox=&category=&limit=` | Historical query (GeoJSON) |
| POST | `/api/sources/{key}/refresh` | Trigger one collection cycle now |
| WS | `/api/ws/live?source=` | Pushes `{new, updated, closed}` diffs each cycle |

`bbox` is `minLon,minLat,maxLon,maxLat`. Times are ISO-8601.

## Adding a data source

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

That's it — the scheduler, ingestion, REST API, WebSocket, and dashboard are all
source-agnostic and pick it up automatically. Moving objects (APRS), evolving
incidents (911), and point readings (weather) all fit the same model.

## Tests

```bash
pytest
```

`normalize` and the pure change-detection rule run offline against a saved payload
fixture (`tests/fixtures/hc911_sample.json`). The full ingest lifecycle test
(`test_ingest_full_lifecycle`) runs only when `DATABASE_URL` is reachable; it is
skipped otherwise.

## Linting & formatting

A [pre-commit](https://pre-commit.com/) hook auto-fixes and lints **staged** code —
`ruff` for Python, `prettier` for the frontend. Enable it once per clone (hooks are
not installed automatically):

```bash
pip install -e ".[dev]"      # pre-commit + ruff
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

## Notes

- **Config / secrets** (`X-Frontend-Auth`, origin, DB URL, tile layer) come from
  `.env` via pydantic-settings — nothing is hardcoded.
- **Be a good upstream citizen**: a descriptive `USER_AGENT` is sent, and the poll
  interval is never set below the source site's own 60s cadence.
- **Retention**: set `RETENTION_DAYS` and add a TimescaleDB
  `add_retention_policy('observations', INTERVAL 'N days')` to auto-drop old
  history (left at keep-forever by default).

## License

LocalDash is licensed under the **GNU Affero General Public License v3.0 or later**
(AGPL-3.0-or-later). See [LICENSE](LICENSE) for the full text.

Because this is an AGPL-licensed network application, if you run a modified version
of LocalDash and let users interact with it over a network, you must also offer those
users the corresponding source code of your modified version.
