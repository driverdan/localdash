## Why

The home page's "Current events" widget shows the next 10 upcoming events regardless of when
they start, so on a busy calendar the at-a-glance list can be dominated by events days out. The
team wants the widget to answer "what's on today?" — retitled "Today's events" and scoped to the
current day.

## What Changes

- Rename the home page events widget heading from "Current events" to "Today's events" (and its
  empty-state copy to match).
- Add a same-day cap to the digest: it renders only events that **start on the viewer's current
  local calendar day**. This is layered on top of the existing fetch — the request, the
  `upcoming` default, the 35-mile cap, and the soonest-first ordering are all unchanged; events
  that start on a later day are simply dropped from the rendered list.

## Capabilities

### New Capabilities
<!-- None: this change modifies an existing capability's requirements. -->

### Modified Capabilities
- `frontend-home`: the events digest widget requirement changes its heading label ("Current
  events" → "Today's events"), its empty-state copy, and its rendered scope (up to 10 upcoming
  events → only those among them that start on the current local day).

## Impact

- `frontend/src/features/home/components/HomePage.svelte` — widget heading and empty-state notice
  copy.
- `frontend/src/features/home/api.ts` — `loadEvents()` filters the fetched items to the current
  local day before assigning `home.events`; the request URL is unchanged.
- `frontend/src/lib/format.ts` — extract the "is this local today?" day check that `fmtEventDate`
  already computes into a small shared helper so the filter and the "Today" label cannot drift.
- No API, DB, or backend changes: the same request is issued; filtering is client-side.
- User-visible only; no breaking changes.
