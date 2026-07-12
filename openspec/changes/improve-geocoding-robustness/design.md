## Context

The single configured source (Tennessee car-events iCal feed) emits `LOCATION` strings shaped
like `"Venue Name, street, city, ST, zip, United States"` — sometimes with the venue slot holding
a duplicate street line or a bare city name. Nominatim free-form search resolves almost none of
these as-is: in the live database 25 of 28 cached lookups failed, leaving 26 of 29 events with a
null location. Null-location events are invisible to the UI distance filter (`ST_DWithin` against
NULL is false) and exempt from the ingest radius filter, so statewide events pile up unlocated
and the events page shows zero results for any distance selection.

Two compounding behaviors in the current code:

- `NominatimGeocoder.geocode()` (app/events/geocoding.py) sends exactly one free-form query per
  address.
- `_geocode()` in app/events/ingest.py caches failures permanently in `geocode_cache`
  (`latitude IS NULL` rows) — a failed address is never queried again, so even a geocoder fix
  won't heal existing data without manual cache surgery.

Constraints: Nominatim's public usage policy (1 req/s, already enforced by the geocoder's slot
rate limiter) applies to every attempt, including fallbacks and retries. Refresh cycles run every
60 minutes and are serialized; the retry pass must not stretch a cycle unboundedly.

## Goals / Non-Goals

**Goals:**

- Raise the geocode success rate for venue-prefixed feed addresses via bounded fallback queries.
- Make cached failures self-healing: periodic, bounded re-attempts that update the cache in place.
- Backfill `events.location` for stored events when their address later resolves, without
  requiring the source to re-report the event.
- Existing stale failures (the 25 rows already cached) become retry-eligible immediately after
  deploy, with no manual intervention.

**Non-Goals:**

- No switch of geocoding provider or use of Nominatim's structured-query API (free-form with
  simplification is enough for this feed's shape; structured parsing of arbitrary source
  addresses is fragile).
- No retroactive application of the ingest radius filter to events that gain a location via
  backfill (the radius spec says stored events are never retroactively removed; keeping that).
- No UI changes (unlocated-event visibility messaging is a separate concern).
- No re-verification of successful lookups; success rows stay permanent.

## Decisions

### 1. Fallback candidates by comma-component stripping, inside `NominatimGeocoder`

`geocode()` builds an ordered candidate list from the comma-split address and queries each until
one resolves:

1. The full address as given.
2. The address with the first component dropped (sheds the venue-name/duplicate-street prefix) —
   only when there are ≥ 4 components, so we don't strip a genuine street address down past
   usefulness.
3. The last 4 components (locality tail: city, ST, zip, country) — a city-centroid result, only
   when there are ≥ 5 components (i.e., something was actually stripped).

Duplicate candidates are dropped. Each attempt goes through the existing `_wait_for_slot()` rate
limiter, so worst case is 3 spaced requests per address. Network/HTTP errors abort the whole
lookup (return None) rather than continuing to fallbacks — a service outage shouldn't triple the
request volume; only an empty result list advances to the next candidate.

**Why inside the geocoder, not ingest**: the cache in `_geocode()` keys on the original address
string and must stay unaware of which variant succeeded; `NullGeocoder` and test fakes are
unaffected.

**Alternative considered**: Nominatim structured queries (`street=`, `city=`, …). Rejected —
requires reliable address parsing we don't have, and free-form with a stripped prefix already
matches how the three current successes resolved.

**Trade-off (accepted)**: a city-centroid fallback locates an event at the city center, not the
venue. For this app's granularity (5–50 mi UI filter, 100 mi ingest radius) that's acceptable and
far better than invisible-to-filtering.

### 2. Retry pass in the refresh cycle, driven by `last_attempted_at`

Add `last_attempted_at` (timestamptz, non-null) to `geocode_cache` via Alembic migration `0004`,
backfilled from `created_at`, with a server default of `now()`. `_geocode()` sets it on insert.

Each refresh cycle (inside the existing `_refresh_lock`, after source ingest) runs a retry pass:

- Select up to `events_geocode_retry_batch` (default 25) rows where `latitude IS NULL` and
  `last_attempted_at` is older than `events_geocode_retry_hours` (default 24; ≤ 0 disables the
  pass), oldest first.
- Re-geocode each through the same geocoder (fallbacks included). On success, write coordinates
  to the row; on failure, bump `last_attempted_at`.
- Stats (`retried`, `resolved`) are logged and returned alongside the existing refresh counts.

**Why in-cycle rather than a separate scheduled job**: reuses the refresh lock (no concurrent
Nominatim clients fighting over the rate limiter), and the batch cap bounds added cycle time to
~25s worst case at 1 req/s.

**Why oldest-first with a bump-on-failure**: guarantees rotation — a permanently unresolvable
address can't starve newer failures, and each address is retried at most once per age window.

**Alternative considered**: treating stale failures as cache misses inline in `_geocode()` during
ingest. Rejected — only re-reported addresses would heal, retry volume would be unbounded within
a cycle, and merge-path lookups would surprise the radius filter.

### 3. Event backfill by address join, same transaction as the cache update

When a retried address resolves, update all events with `address = <cached address>` and
`location IS NULL` to the new point (same `SRID=4326;POINT(lon lat)` WKT construction ingest
uses). This heals events whose sources have stopped reporting them — the merge-path backfill in
ingest only helps while a feed still lists the event.

Backfilled events are **not** run through the ingest radius filter (see Non-Goals); the events
listing API's `ST_DWithin` filter naturally handles far-away ones at query time.

### 4. Config

Two new settings beside the existing geocoder settings in `app/config.py`:

- `events_geocode_retry_hours: float = 24` — minimum age of a failure before re-attempt; ≤ 0
  disables the retry pass entirely.
- `events_geocode_retry_batch: int = 25` — max failures re-attempted per refresh cycle.

Fallback behavior is not configurable — it's a correctness fix, not a tunable.

## Risks / Trade-offs

- [City-centroid coordinates misrepresent venue location] → Accepted for this app's coarse
  distance granularity; the locality tail is only attempted after more specific candidates fail.
- [Extra Nominatim volume from fallbacks/retries] → Bounded: ≤ 3 requests per address, retry
  batch capped per cycle, all behind the existing 1 req/s limiter; failures back off to one
  attempt per `retry_hours` window.
- [Fallback resolves to a wrong-but-plausible place (e.g., same-named city in another state)] →
  Candidates always retain the state/zip tail, which anchors Nominatim; the ingest radius filter
  still drops far-geocoding *new* events.
- [Retry pass lengthens the refresh cycle] → ≤ ~25 s at defaults; runs under the existing lock so
  nothing interleaves; batch cap is configurable down.
- [Backfill sets locations for events the radius filter would have dropped at ingest] → Matches
  the existing spec rule that stored events are never retroactively removed; the listing API
  filters them out by distance anyway.

## Migration Plan

1. Migration `0004` adds `last_attempted_at` with backfill from `created_at` (downgrade drops the
   column). Existing failure rows are all older than 24 h, so the first refresh after deploy
   retries up to 25 of them — the current 25 stale failures heal within one or two cycles with no
   manual step.
2. Code and migration deploy together (existing docker-entrypoint runs `alembic upgrade head`).
3. Rollback: revert code and downgrade the migration; cache rows updated in the meantime keep any
   coordinates they gained (harmless).

## Open Questions

None — sized and defaulted to the current single-feed reality; revisit the retry batch cap if
many high-volume sources are added later.
