## Why

Events ingest stores everything a source returns — there is no geographic gate. That was fine
while every configured source was Chattanooga-local, but regional/statewide feeds break the
assumption: the verified statewide Tennessee car-events iCal feed (companion change
`add-tn-car-events-ical-feed`) is roughly 80% non-Chattanooga events (Clarksville, Memphis,
White House, ...). Today those events are merely hidden by the read API's `max_miles` filter,
but they still consume rate-limited Nominatim geocoding lookups, permanent `geocode_cache`
rows, and `events` rows forever (events are never purged). An ingest-side radius filter keeps
the DB and geocoder budget scoped to the area the dashboard actually serves, for this feed and
any future regional source.

## What Changes

- New setting `events_ingest_max_miles` in `app/config.py` (default 50, matching the existing
  `MEETUP_RADIUS_MILES`; `0` disables filtering entirely).
- `upsert_raw_events()` in `app/events/ingest.py` drops a **new** raw event when its geocoded
  coordinates are farther than `events_ingest_max_miles` from `CHATTANOOGA_CENTER`
  (haversine in Python — the coords are already floats in hand).
- Events that have no address or whose address fails to geocode are **kept** (unchanged from
  today's behavior): we cannot prove they are far, and the read API already handles unlocated
  events.
- The merge path is unchanged: an already-stored event that later geocodes far is not retro-
  actively removed (kept deliberately simple; existing rows were admitted under prior rules).
- Ingest stats gain a `skipped_far` count alongside `created`/`merged`, surfaced through
  `run_sources()` and the existing `POST /api/v1/events/refresh` response, and logged.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `events`: cross-source ingest gains a configurable radius gate — new events whose geocoded
  location is beyond `events_ingest_max_miles` of the Chattanooga center are not stored;
  unlocated events are still stored; refresh reporting includes the skipped count.

## Impact

- **Code**: `app/config.py` (one setting), `app/events/ingest.py` (distance check + stats
  key, plus a small haversine helper), `app/api/events.py` only if the refresh response model
  enumerates keys (it passes the stats dict through today).
- **API**: `POST /api/v1/events/refresh` response gains `skipped_far`; no other API changes.
- **DB / migrations**: none — this reduces rows written, changes no schema.
- **Behavior**: far-away events from regional feeds (notably the TN car-events feed) no longer
  appear in the DB at all; deployments wanting statewide data set `events_ingest_max_miles=0`.
- **Tests**: new offline ingest tests with a fake geocoder covering drop/keep/disable paths
  and the `skipped_far` stat.
