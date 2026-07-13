## 1. Schema and config

- [x] 1.1 Add `last_attempted_at` (timezone-aware, non-null, server default now) to the
  `GeocodeCache` model in `app/events/models.py`
- [x] 1.2 Write Alembic migration `0004`: add `geocode_cache.last_attempted_at` backfilled from
  `created_at`; downgrade drops the column
- [x] 1.3 Add `events_geocode_retry_hours` (float, default 24) and `events_geocode_retry_batch`
  (int, default 25) to `app/config.py` beside the existing geocoder settings

## 2. Fallback geocoding

- [x] 2.1 Add candidate-generation to `app/events/geocoding.py`: full address, venue-stripped
  variant (≥ 4 comma components), locality tail of last 4 components (≥ 5 components), with
  duplicates removed
- [x] 2.2 Rework `NominatimGeocoder.geocode()` to try candidates in order — each attempt through
  `_wait_for_slot()`, advancing only on an empty result, aborting on network/HTTP error
- [x] 2.3 Unit tests: venue-prefixed address falls back and resolves; double-fallback to locality
  tail; short addresses generate no fallbacks; duplicate candidates skipped; service error stops
  the fallback chain; fallback attempts respect the rate-limit interval

## 3. Failure retry pass

- [x] 3.1 Set `last_attempted_at` on new cache rows in `_geocode()` (`app/events/ingest.py`)
- [x] 3.2 Implement the retry pass in `app/events/ingest.py`: select up to the batch cap of
  coordinate-less cache rows older than the retry age (oldest first), re-geocode, update the row
  (coords on success, bumped `last_attempted_at` on failure), return `retried`/`resolved` counts
- [x] 3.3 Backfill locations: on retry success, set `location` for events matching the cached
  address with null location, using the same WKT point construction as ingest
- [x] 3.4 Wire the retry pass into `refresh()` (`app/events/refresh.py`) after `run_sources`,
  inside `_refresh_lock`, gated on `events_geocode_retry_hours > 0`; include retry stats in the
  log line and returned dict
- [x] 3.5 Tests: stale failure retried and cache updated; matching null-location events
  backfilled (and located events untouched); fresh failures skipped; failed retry bumps
  `last_attempted_at`; batch cap enforced oldest-first; non-positive retry age disables the
  pass; success rows never re-queried

## 4. Verify end to end

- [x] 4.1 Run the full test suite
- [x] 4.2 Rebuild the Docker stack (`sg docker -c 'docker compose up --build -d'`), confirm
  migration 0004 applied and existing failure rows have `last_attempted_at` backfilled
- [x] 4.3 Trigger `POST /api/v1/events/refresh`, confirm previously failed addresses resolve
  (cache rows gain coordinates, events gain locations) and the UI distance filter returns
  results for nearby-radius data
