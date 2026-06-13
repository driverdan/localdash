# LocalDash

Store, serve, and view **time-series geolocation data** in a web dashboard. The
first data source is **active 911 incidents** for Hamilton County, TN; the design
is source-agnostic so APRS, weather, and other real-time/historical geo feeds can
be added by writing one small collector class.

## How it works

```
collector.fetch() ── raw payload
        │
   normalize() ──── list[NormalizedObservation]   (source-agnostic)
        │
   ingest() ─────── upsert entity · append observation on change · close on absence
        │
   ┌────┴─────┐
 REST API   WebSocket diffs ──► Leaflet dashboard (map + filters + live table)
```

The upstream 911 endpoint returns only a **snapshot** of currently-active calls.
LocalDash builds the **time-series** itself: a background scheduler polls every
60s, tracks each incident by `master_incident_id`, appends an observation row
whenever its status or position changes, and marks it closed when it drops out of
the feed.

The upstream feed is documented in [`docs/hc911-api.md`](docs/hc911-api.md)
(endpoint, headers, field reference, and behavioral caveats).

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
```

## API

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/config` | Frontend bootstrap (map tiles) |
| GET | `/api/sources` | Registered sources + last-run status |
| GET | `/api/active?source=&category=&bbox=` | Active entities as GeoJSON |
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

## Notes

- **Config / secrets** (`X-Frontend-Auth`, origin, DB URL, tile layer) come from
  `.env` via pydantic-settings — nothing is hardcoded.
- **Be a good upstream citizen**: a descriptive `USER_AGENT` is sent, and the poll
  interval is never set below the source site's own 60s cadence.
- **Retention**: set `RETENTION_DAYS` and add a TimescaleDB
  `add_retention_policy('observations', INTERVAL 'N days')` to auto-drop old
  history (left at keep-forever by default).
