## Why

LocalDash covers local incidents (timeseries map) and local news, but nothing answers "what's
happening in Chattanooga?" A working PoC (`../chattevents`) already aggregates area events —
de-duplicating cross-source listings, tagging them by topic, and geocoding venues — but it lives as
a separate stack (sync FastAPI + React + its own Postgres). Porting it into LocalDash as a third
feature (the same move that brought ChattNews in as `news`) gives one dashboard, one database, one
deploy — and upgrades the PoC onto PostGIS and the async stack.

## What Changes

- New backend feature package `app/events/`: pluggable `EventSource` interface, ingest/merge
  pipeline (canonical-key de-duplication, field backfill, one link per source), keyword topic
  tagging, and Nominatim geocoding with a DB-backed cache — ported from the chattevents PoC and
  adapted sync→async (async SQLAlchemy + httpx / thread offload; Postgres-only, SQLite support
  dropped).
- New tables `events`, `event_links`, `tags`, `event_tags`, `geocode_cache` (plain relational,
  hand-written raw-SQL migration `0003`). Event location becomes a PostGIS geometry point (replacing
  the PoC's lat/lon floats); distance filtering moves into SQL (`ST_DWithin`). Events are retained
  indefinitely — no purge/retention policy.
- New API namespace `/api/v1/events/`: `GET /items` (filters: topic tags, distance from an origin
  defaulting to the Chattanooga center, upcoming-only default, title search), `GET /tags`,
  `POST /refresh` (asyncio-lock serialized with the scheduled job, like news).
- New APScheduler refresh job polling all configured sources on an interval (new
  `events_enabled` / `events_refresh_minutes` settings, plus the source settings above).
- New frontend feature `frontend/src/features/events/` on a new `/events` route: event list with
  topic chips, distance filter, title search, and per-source origin links (runes store, fetch +
  periodic reload, no WebSocket). Nav header gains an "Events" link.
- The PoC's two concrete sources are ported as well: a generic **iCal feed source** (any `.ics`
  URL; feeds configured via a new `events_ical_feeds` setting, comma-separated, default empty) and
  a **Meetup source** (Meetup GraphQL `keywordSearch` within a radius of the Chattanooga center;
  registered only when `events_meetup_token` is set, with an optional `events_meetup_query`
  keyword filter). Both emit addresses only — coordinates always come from the ingest geocoder.
  Nothing is configured by default, so the feature starts empty until the operator sets feeds or a
  token. Tests use fake/sample sources (per the PoC's `tests/sample_sources.py` pattern) plus
  offline parse fixtures for iCal and Meetup.
- Known PoC caveat carried over deliberately: the dedup key buckets by start *hour*, so the same
  event listed at 7:59 and 8:01 does not merge. Geocoding has no rate throttling beyond the
  permanent cache. Both are future improvements, not part of this change.

## Capabilities

### New Capabilities

- `events`: backend event aggregation — source interface with config-driven iCal and Meetup
  sources, dedup/merge ingest, topic tagging, geocoding with cache, storage, scheduler job, and
  the `/api/v1/events/` API.
- `frontend-events`: the `/events` page — event list UI with topic/distance/search filtering and
  source links, following the feature-namespace and runes-store conventions.

### Modified Capabilities

- `frontend-shell`: the client-side route table requirement currently fixes the routes to `/`
  (news) and `/map` (timeseries); it gains `/events` (events feature) and a nav header link.

## Impact

- **Code:** new `app/events/` package and `app/api/events.py` router (+ one `include_router` line
  in `app/main.py`); one scheduler job in `app/scheduler.py`; new settings in `app/config.py`; new
  `frontend/src/features/events/` folder + one route entry and nav link in `App.svelte`.
- **Database:** migration `0003` adds five tables; no changes to existing tables. PostGIS is
  already installed (used by timeseries).
- **Dependencies:** one new — `icalendar` for ICS parsing; httpx, SQLAlchemy, APScheduler already
  present.
- **External services:** OpenStreetMap Nominatim for geocoding (cached permanently per address;
  subject to its usage policy — descriptive User-Agent required); configured iCal feed hosts; the
  Meetup GraphQL API when a token is configured.
- **APIs:** additive only (`/api/v1/events/*`); no existing endpoint changes.
