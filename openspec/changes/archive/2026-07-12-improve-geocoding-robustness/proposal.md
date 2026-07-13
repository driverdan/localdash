## Why

~90% of ingested event addresses currently fail to geocode (25 of 28 cached lookups), because the
iCal feed emits venue-name-prefixed free-form strings ("O'Charley's on Riverside, 674 N Riverside
Drive, Clarksville, TN, …") that Nominatim's free-form search cannot resolve. Failures are cached
permanently, so a failed address is never tried again — even after the geocoder improves. The
result is visible today: events with null locations are invisible to the UI distance filter and
exempt from the ingest radius filter, so the events page shows nothing for any distance choice.

## What Changes

- **Fallback geocoding queries**: when the full address string fails, the Nominatim geocoder
  retries with progressively simplified variants — first with the leading (venue-name) component
  stripped, then with only the locality tail (city, state, zip, country). Each attempt still
  respects the rate-limit interval; attempts per address are bounded.
- **Failed lookups become retryable**: `geocode_cache` failure rows gain a last-attempt timestamp.
  Each refresh cycle re-attempts a bounded batch of failures whose last attempt is older than a
  configurable age, updating the cache row in place (coordinates on success, a fresh attempt
  timestamp on failure). Successful lookups remain permanent and are never re-queried.
- **Event backfill on retry success**: when a retried address resolves, stored events that carry
  that address and a null location get their location populated — no re-report from a source is
  required.
- New settings: retry age threshold and per-cycle retry batch cap (non-positive age disables
  retries).
- Alembic migration adding the last-attempt column to `geocode_cache`, backfilled from
  `created_at` so existing stale failures become eligible for retry immediately.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `events`: the "Address geocoding with a permanent cache" requirement changes — the cache is
  permanent for successes but retryable for failures, and geocoding gains fallback query
  simplification. A new requirement covers the refresh-cycle retry pass and event location
  backfill.

## Impact

- `app/events/geocoding.py`: candidate-query generation and fallback loop in `NominatimGeocoder`.
- `app/events/ingest.py` / `app/events/refresh.py`: retry pass wiring in the refresh cycle;
  cache-row updates and event backfill.
- `app/events/models.py` + new Alembic migration `0004`: `geocode_cache.last_attempted_at`.
- `app/config.py`: two new settings (`events_geocode_retry_hours`, `events_geocode_retry_batch`).
- Nominatim usage: bounded extra requests (max ~3 per new address, capped retry batch per cycle),
  still spaced by the existing rate limiter.
- No API or frontend changes; the distance filter starts working as data heals.
