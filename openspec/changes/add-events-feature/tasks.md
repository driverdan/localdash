## 1. Branch & schema

- [x] 1.1 Create branch `add-events-feature` (never commit to main)
- [x] 1.2 Write migration `alembic/versions/0003_events.py` (raw SQL): `events` (canonical_key
      unique, TIMESTAMPTZ starts_at indexed / ends_at, nullable `location GEOMETRY(POINT,4326)`
      + GIST index), `event_links` (FK cascade, UNIQUE(event_id, source_name)), `tags`,
      `event_tags`, `geocode_cache` (unique address, nullable coords); downgrade drops all five
- [x] 1.3 Run `alembic upgrade head` against the dev DB and verify `downgrade -1` / re-upgrade

## 2. Events package — pure logic (ported with tests)

- [x] 2.1 Create `app/events/__init__.py`; port `dedup.py` (normalize_title, canonical_key) and
      `tagging.py` (TOPIC_KEYWORDS, tag_event/tag_text) verbatim from the PoC
- [x] 2.2 Port the PoC's dedup and tagging tests into `tests/test_events_dedup.py` and
      `tests/test_events_tagging.py` (pure/offline, no DB)
- [x] 2.3 Add `app/events/sources/base.py`: `RawEvent` dataclass (address-only, no coords) and
      `EventSource` ABC with async `fetch()`

## 3. Concrete sources — iCal & Meetup (ported with tests)

- [x] 3.1 Add `icalendar` to `pyproject.toml` dependencies
- [x] 3.2 Port `app/events/sources/ical.py`: async httpx fetch + pure `parse()` of VEVENTs
      (summary/description, DTSTART required — skip undated, date-only → midnight, coerce to
      aware UTC, LOCATION → venue+address, UID → source_event_id, URL fallback to feed URL)
- [x] 3.3 Port `app/events/sources/meetup.py`: keywordSearch GraphQL POST via httpx (bearer token,
      lat/lon/50-mile radius around the Chattanooga center constant, optional keyword query,
      first=50) + pure `parse()` (Event results with id+date only, aware-UTC times, group-name
      description prefix, venue address/city/state → address with venue-name fallback)
- [x] 3.4 Add `app/events/sources/__init__.py`: `build_sources(settings)` — one ICalSource per
      `events_ical_feeds` URL, MeetupSource iff `events_meetup_token` is set, `[]` when nothing
      is configured; no fixture/sample sources importable by the app
- [x] 3.5 Port the PoC's iCal parse tests and Meetup tests (parse fixtures, address formatting,
      skip undated/non-Event results, token-gated registration) into `tests/test_events_ical.py`
      and `tests/test_events_meetup.py` (offline, no network)

## 4. Events package — models, geocoding, ingest

- [x] 4.1 Add `app/events/models.py`: Event (Geometry POINT location via GeoAlchemy2), EventLink,
      Tag + event_tags, GeocodeCache — matching migration 0003
- [x] 4.2 Add `app/events/geocoding.py`: Geocoder ABC, NullGeocoder, NominatimGeocoder on
      `httpx.AsyncClient` with configurable User-Agent (`events_geocoder_user_agent` setting)
- [x] 4.3 Add `app/events/ingest.py`: async port of the PoC manager — geocode-with-cache helper
      (in-run dict + geocode_cache table, failures cached), `upsert_raw_events` (create/tag or
      merge/backfill + per-source link upsert, eager-loaded relationships — no lazy loads under
      asyncio), `run_sources` with per-source error isolation; returns `{created, merged}`
- [x] 4.4 Add `app/events/refresh.py`: asyncio-lock-serialized refresh cycle mirroring
      `app/news/refresh.py`
- [x] 4.5 Port the ingest tests to `tests/test_events_ingest.py` using fake sources and a fake
      geocoder (dedup across sources, backfill, link refresh, failing source isolation, geocode
      cache hit/failure-cached, idempotent re-ingest) — DB-backed tests auto-skip without
      `DATABASE_URL`, per the `conftest.py` fixture pattern

## 5. Config, scheduler, API

- [x] 5.1 Add settings to `app/config.py`: `events_enabled` (true), `events_refresh_minutes` (60),
      `events_geocoder_user_agent`, `events_ical_feeds` (""), `events_meetup_token` (""),
      `events_meetup_query` (""); document them in `.env.example`
- [x] 5.2 Register the `events_refresh` job in `app/scheduler.py` startup (max_instances=1, run
      once at startup), gated by `events_enabled`
- [x] 5.3 Add `app/api/events.py` router + `include_router` in `app/main.py`:
      `GET /api/v1/events/items` (topic[], max_miles, lat/lon origin defaulting to the Chattanooga
      center constant, upcoming=true, search, limit=500; SQL filtering with ST_DWithin and
      ST_Distance-derived `distance_miles`, tags join, ILIKE), `GET /api/v1/events/tags`,
      `POST /api/v1/events/refresh`
- [x] 5.4 Add `tests/test_api_events.py` (DB-backed, auto-skip): default upcoming listing + order,
      distance filter excludes far/unlocated, multi-topic OR filter, search, tags endpoint,
      refresh endpoint counts

## 6. Frontend

- [x] 6.1 Create `frontend/src/features/events/`: types + API module (`/api/v1/events/`),
      `store.svelte.ts` runes store (items, tags, filters, status, 5-minute auto-reload),
      `index.ts` public surface
- [x] 6.2 Build components: topic chips (multi-select), max-distance control, title search box,
      event list cards (title, time, venue, tags, distance_miles, one link per source), explicit
      empty state; filter changes refetch with query params
- [x] 6.3 Wire the route: `/events` entry + "Events" nav link in `App.svelte` (import only the
      feature's `index.ts`; no changes inside `lib/` beyond none-needed router reuse)
- [x] 6.4 `npm run check` passes with 0 errors; `npm run build` produces a working bundle

## 7. Verify & ship

- [x] 7.1 Full `pytest` green (DB tests running against `docker compose up -d db` +
      `alembic upgrade head`)
- [x] 7.2 Rebuild and run the stack (`sg docker -c 'docker compose up --build'`); verify `/events`
      deep-link + nav, empty state, and `POST /api/v1/events/refresh` returns zero counts with no
      sources configured
- [ ] 7.3 Optional smoke test: set `events_ical_feeds` to a known-good `.ics` URL and verify a
      refresh ingests, tags, geocodes, and lists real events
- [x] 7.4 Commit to the branch, push, and open a PR
