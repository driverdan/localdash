## Context

LocalDash has two features — `timeseries` (geo pipeline: collectors → ingest → hypertable → map)
and `news` (RSS aggregator ported from the standalone ChattNews app). This change adds a third,
`events`, ported from the standalone PoC at `../chattevents`: an event aggregator that
de-duplicates the same real-world event reported by multiple sources, tags events by topic via
keyword matching, geocodes venue addresses through Nominatim with a permanent DB cache, and serves
a filterable list API.

The PoC is a sync stack (FastAPI + sync SQLAlchemy + `requests`, SQLite-or-Postgres, React SPA).
LocalDash is async (SQLAlchemy 2.0 async + asyncpg, httpx, APScheduler in the event loop,
Svelte 5 + TS). The news port established the playbook this change follows: feature package under
`app/`, one router in `app/api/`, one scheduler job, raw-SQL migration, feature folder under
`frontend/src/features/`, refresh serialized by an asyncio lock.

The change ships the pipeline, storage, API, and UI together with the PoC's two concrete sources —
generic iCal feeds and Meetup — both config-driven and off by default, so the feature starts empty
until the operator configures feed URLs or a Meetup token.

## Goals / Non-Goals

**Goals:**
- Port the chattevents pipeline (dedup, tagging, geocoding+cache, merge/upsert ingest) into
  `app/events/` on the async stack, preserving the PoC's behavior and porting its offline tests.
- Store events in Postgres with a PostGIS geometry location; filter by distance in SQL.
- Serve `/api/v1/events/` (items, tags, refresh) and an `/events` page in the SPA.
- Port the PoC's iCal and Meetup sources, activated purely by configuration (no defaults), and
  keep the source interface pluggable so further sources are additive only.

**Non-Goals:**
- No default/bundled feed list — a curated Chattanooga feed registry is future work; sources
  activate only via explicit configuration.
- No dedup improvements (hour-bucket key ported as-is) and no geocoding rate throttling beyond the
  permanent cache.
- No retention/purge policy — events are kept indefinitely.
- No map integration (events do not appear on `/map`; no GeoJSON layer endpoint).
- No WebSocket — the events UI polls like news.

## Decisions

### 1. Sibling feature, not a collector
Events do not flow through `collectors/` + `ingest.py`. The timeseries model tracks *state of an
entity over time* (open → moved → closed); an event is a future-dated item whose core semantics are
cross-source *merging* (one canonical record, N source links). That is the news shape, not the
entity/observation shape. Alternative considered: modeling events as entities with one observation —
rejected because dedup-by-canonical-key, tag join tables, and field backfill have no home in the
source-agnostic ingest, and closure sweeps would wrongly "close" events absent from one source.

### 2. Package layout mirrors `app/news/`
```
app/events/
  models.py      Event, EventLink, Tag (+ event_tags), GeocodeCache
  dedup.py       normalize_title, canonical_key   (pure — ported verbatim)
  tagging.py     TOPIC_KEYWORDS, tag_event        (pure — ported verbatim)
  geocoding.py   Geocoder ABC, NullGeocoder, NominatimGeocoder (httpx.AsyncClient)
  sources/
    base.py      RawEvent dataclass, EventSource ABC (async fetch())
    ical.py      ICalSource — one instance per configured .ics URL
    meetup.py    MeetupSource — Meetup GraphQL keywordSearch
    __init__.py  build_sources(settings) — the registry, built from config
  ingest.py      upsert_raw_events / run_sources  (async port of PoC manager.py)
  refresh.py     asyncio-lock-serialized refresh cycle (mirrors news/refresh.py)
app/api/events.py  router: GET /items, GET /tags, POST /refresh
```
`build_sources()` is the counterpart of `build_collectors()` / the news registry: it creates one
`ICalSource` per URL in `events_ical_feeds` and a `MeetupSource` iff `events_meetup_token` is set,
returning `[]` when nothing is configured. Fixture/sample sources live only in the test suite (the
PoC's rule: seed data can never reach production).

### 3. Sync→async port strategy
- DB access: async SQLAlchemy sessions (`app.db.SessionLocal`), same as news. The PoC's ORM-heavy
  merge logic (lazy `event.links`, `event.tags` appends) is rewritten with explicit
  `selectinload`/awaited queries — lazy loading doesn't fly under asyncio.
- HTTP: `EventSource.fetch()` becomes `async def`; the Nominatim geocoder, iCal feed fetches, and
  the Meetup GraphQL POST all use `httpx.AsyncClient`. (No `to_thread` escape hatch needed — that
  was for feedparser's network handling; `icalendar` only parses bytes we already fetched.)
- Pure modules (`dedup`, `tagging`) stay synchronous and are ported with their tests, as are the
  sources' pure `parse()` halves (the PoC's fetch/parse split is kept for offline testability).
- Datetime coercion in the sources changes from the PoC's naive-UTC to timezone-aware UTC,
  matching the `TIMESTAMPTZ` schema; date-only iCal starts still become local midnight.
- Postgres-only: the PoC's SQLite dual-support (naive datetimes, Float coords) is dropped.

### 4. PostGIS geometry + SQL filtering (replaces floats + Python haversine)
`events.location` is `GEOMETRY(POINT, 4326)` (nullable — ungecoded events have no point), with a
GIST index, matching the timeseries schema style. The list query filters and computes distance in
SQL: `ST_DWithin(location::geography, origin::geography, meters)` for `max_miles`, and
`ST_Distance(...)::geography` converted to miles for the response's `distance_miles`. Topic and
title filters also move into SQL (join through `event_tags`, `ILIKE`) instead of the PoC's
load-everything-then-filter-in-Python repository. Rationale: Postgres-only removes the reason the
PoC did Python-side filtering, and SQL filtering is the house style (the timeseries API does bbox
in SQL). The PoC's haversine tests are superseded by API-level distance tests.

### 5. Data model (migration `0003`, raw SQL per repo convention)
Five tables, plain relational like news (no hypertable — events are not time-series):
- `events`: id, `canonical_key` (unique), title, description, `starts_at TIMESTAMPTZ` (indexed),
  `ends_at TIMESTAMPTZ NULL`, venue_name, address, `location GEOMETRY(POINT,4326) NULL`,
  created_at/updated_at.
- `event_links`: event_id FK (cascade), source_name, source_url, source_event_id;
  `UNIQUE(event_id, source_name)`.
- `tags` (kept as a table per decision): id, unique name. `event_tags` join table.
- `geocode_cache`: unique address → nullable lat/lon (a null-coords row records a failed lookup so
  it is never retried), created_at.
Timestamps become `TIMESTAMPTZ` (house style, news precedent) instead of the PoC's naive UTC; the
dedup key formats the start time in UTC so key stability is preserved.

### 6. Dedup/merge semantics ported as-is
`canonical_key = sha256(normalized_title | start-time UTC 'YYYY-MM-DDTHH')[:32]`. On ingest: new
key → insert + geocode + tag; existing key → merge (backfill empty description/venue/address,
geocode if still unlocated) and upsert the per-source link (refresh URL if the source already
linked). One source failing must not abort the others (news-style error isolation). Known carried
caveat: listings straddling an hour boundary don't merge.

### 7. Geocoding: Nominatim + permanent cache, no throttling (yet)
Ported behavior: check in-run dict cache → `geocode_cache` table → call Nominatim (descriptive
User-Agent from config) → cache result permanently, including failures. No rate limiting in this
change — acceptable while zero sources are registered; flagged as a prerequisite improvement for
the sources change (see Risks).

### 8. API shape: plain JSON, not GeoJSON
`GET /api/v1/events/items` returns `{count, origin, items: [...]}` where each item carries title,
times, venue/address, `latitude`/`longitude` (extracted via `ST_Y`/`ST_X`, null when ungecoded),
sorted tag names, all source links, and `distance_miles`. The repo's "geographic responses are
GeoJSON" convention applies to map-layer endpoints; this is a listing API whose primary consumer
is a list UI, and many events lack coordinates. If events later join the map, a GeoJSON endpoint
is an additive follow-up. Query params: repeatable `topic`, `max_miles` + optional `lat`/`lon`
origin (default: Chattanooga center constant), `upcoming` (default true → `starts_at >= now()`),
`search` (title ILIKE), `limit` (default 500).
`GET /api/v1/events/tags` lists known tag names. `POST /api/v1/events/refresh` runs a cycle
through the same asyncio lock as the scheduled job and reports `{created, merged}`.

### 9. Scheduler + config
One APScheduler job (id `events_refresh`, `max_instances=1`, run-at-startup) added in
`scheduler.py`'s startup path, gated by `events_enabled` (default true) with interval
`events_refresh_minutes` (default 60, matching the PoC's hourly cadence). New settings in
`config.py`: `events_enabled`, `events_refresh_minutes`, `events_geocoder_user_agent`, plus the
source knobs — `events_ical_feeds` (comma-separated `.ics` URLs, default empty),
`events_meetup_token` (empty = Meetup source not registered), `events_meetup_query` (optional
keyword filter). The Chattanooga center and the Meetup search radius (50 miles) live as code
constants in `app/events/` (not config), as in the PoC.

### 10. iCal and Meetup sources ported with their fetch/parse split
`ICalSource` fetches a `.ics` URL and parses `VEVENT`s with `icalendar` (new dependency): summary →
title (fallback "Untitled event"), `DTSTART` required (undated components skipped; date-only values
become midnight), `LOCATION` supplies both venue name and geocodable address, `UID` →
source_event_id, per-event `URL` falling back to the feed URL. `MeetupSource` posts the PoC's
`keywordSearch` GraphQL query (lat/lon/radius filter around the Chattanooga center, `first=50`)
with the bearer token, keeps only `Event` results with an id and date, prefixes the group name onto
the description, and builds the address string from venue address/city/state (falling back to the
venue name). Both emit `RawEvent`s with addresses only — geocoding stays centralized in ingest.
Each source's `parse()` is a pure function of fetched bytes/JSON, tested offline against fixtures
(the PoC's tests port directly).

### 11. Frontend: `features/events/` mirroring `features/news/`
Runes store (`store.svelte.ts`) holding items/tags/filters + load status; API module; components
for topic chips, distance select, search box, and the event list (each card shows time, venue,
tags, and one link per source). Filters map to query params and trigger a server-side refetch (the
PoC behavior) — no client-side filtering of a cached superset. Auto-reload every 5 minutes like
news. Route: `/events` added to `App.svelte`'s route table + one nav header link. Import rules
unchanged: the feature imports only itself and `lib/`.

## Risks / Trade-offs

- [Nominatim has a 1 req/s usage policy and no throttling is implemented (kept as-is per
  decision)] → The permanent cache bounds steady-state volume near zero; the exposure is the
  *first* ingest after configuring a feed with many unlocated events, which can burst requests.
  Mitigations available today: enable feeds one at a time and let the cache warm. Proper
  throttling remains flagged future work and should precede any large default feed registry.
- [Feature ships empty unless configured — no feeds or token are set by default] → Accepted and
  intentional (mirrors the PoC). The UI shows an honest empty state; tests exercise the pipeline
  with fake sources and offline iCal/Meetup parse fixtures.
- [Meetup GraphQL fetch is unpaginated (first=50, PoC behavior)] → Ported as-is; busy areas beyond
  50 results are silently truncated. Acceptable for Chattanooga's volume; pagination is a small
  follow-up if it ever binds.
- [Hour-bucket dedup key misses near-boundary duplicates] → Known PoC caveat, ported deliberately;
  fixing it changes canonical keys (re-keying existing rows), so it's isolated as future work.
- [ORM lazy-loading patterns from the PoC don't work under async sessions] → Merge logic is
  restructured around eager loads; the ported ingest tests (create/merge/backfill/link-refresh)
  guard behavioral parity.
- [Failed geocodes are cached forever, so a transient Nominatim outage permanently null-locates an
  address] → Ported as-is (PoC behavior); rows can be deleted manually to retry. Revisit alongside
  throttling as future work.

## Migration Plan

1. Migration `0003_events.py` (raw SQL upgrade/downgrade) creates the five tables + indexes;
   `alembic upgrade head` runs automatically in the Docker entrypoint. Downgrade drops them.
2. Additive only — no existing tables, endpoints, or frontend routes change (nav gains a link).
   Rollback = revert the PR and `alembic downgrade`.

## Open Questions

None — decisions above were settled during exploration with the user (PostGIS: yes; retention:
indefinite; route: `/items`; tags table: kept; iCal + Meetup sources: included, config-driven with
no defaults).
