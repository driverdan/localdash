## Why

The home page's events digest is labeled "Upcoming events" and shows only 5 rows. The team
wants the widget titled "Current events" and to surface more of what's happening — a fuller
list of 10 — so the homepage is more useful at a glance.

## What Changes

- Rename the home page events widget heading from "Upcoming events" to "Current events".
- Increase the number of events the widget requests and renders from 5 to 10.
- Update the widget's empty-state / narrative copy so it stays consistent with the new label.

## Capabilities

### New Capabilities
<!-- None: this change modifies an existing capability's requirements. -->

### Modified Capabilities
- `frontend-home`: the home events digest widget requirement changes its heading label
  ("Upcoming events" → "Current events") and its item count (up to 5 → up to 10 events).

## Impact

- `frontend/src/features/home/components/HomePage.svelte` — widget heading text (and the
  empty-state notice copy).
- `frontend/src/features/home/api.ts` — `loadEvents()` request limit (`?limit=5` → `?limit=10`)
  and its accompanying comment.
- No API, DB, or backend changes: the events endpoint already accepts an arbitrary `limit`.
- User-visible only; no breaking changes.
