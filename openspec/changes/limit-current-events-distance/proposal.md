## Why

The home page's "Current events" digest fetches events with no distance filter, so a
sparse local calendar can push distant events (100+ miles away, up to the ingest cap) into
the at-a-glance list. The digest should stay local — capping it at 35 miles keeps the
homepage showing what's actually nearby.

## What Changes

- The home "Current events" widget's request gains a fixed `max_miles=35` distance filter
  (origin = the configured center), so only events within 35 miles of the center appear in
  the digest.
- Saved topic and search filters from the events page remain ignored; the distance cap is a
  fixed homepage value, not the user's persisted `maxMiles` preference.

## Capabilities

### New Capabilities

<!-- None -->

### Modified Capabilities

- `frontend-home`: the "Current events digest widget" requirement changes from fetching with
  no distance parameter to always fetching with a fixed `max_miles=35`.

## Impact

- `frontend/src/features/home/api.ts` — `loadEvents` request URL gains `&max_miles=35`.
- No backend change: `GET /api/v1/events/items` already accepts `max_miles` and defaults the
  distance origin to `settings.center`.
- No new dependencies; frontend rebuild only.
