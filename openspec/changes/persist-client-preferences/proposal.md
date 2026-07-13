# Proposal: persist-client-preferences

## Why

Filter and view selections live only in in-memory Svelte state, so a page refresh (or closing the
tab) silently resets every page to defaults — a user who curates map sources or news settings loses
that work on every reload. Persisting these preferences client-side makes the dashboard remember
how each browser wants to see it, with no backend or account machinery.

## What Changes

- Add a small localStorage-backed preferences module in the frontend, with one storage key per
  feature (`localdash.map`, `localdash.events`, `localdash.news`) and a tolerant reader that
  ignores malformed or unknown data.
- Persist, per page:
  - **Map**: `selectedSources`, `categories`, `showClosed`, `closedWindow`
  - **Events**: `topics`, `maxMiles`
  - **News**: `activeTab`, `hours`, `multiOnly`
- Ephemeral state (`search`, `status`, `jurisdiction`, `detailId`, live data, connection state) is
  deliberately NOT persisted.
- Saved sources/categories are an explicit allowlist: with no saved preferences, everything
  defaults on (today's behavior); once preferences exist, sources/categories added to the app
  later default to unchecked. On load, saved lists are intersected with currently-known
  sources/categories to drop stale keys.
- Preferences are saved on any change (first toggle opts the browser into allowlist mode).
- Add a "Reset filters" affordance on the map page that clears the stored key and restores
  dynamic-default behavior (all sources/categories on, including future ones).

## Capabilities

### New Capabilities

- `frontend-preferences`: client-side persistence of per-feature view preferences — storage keys,
  serialization, tolerant loading, allowlist semantics for saved source/category selections, and
  reset-to-defaults behavior.

### Modified Capabilities

- `frontend-timeseries`: filtering requirement changes — source/category checkboxes, show-closed
  toggle, and closed-window selector initialize from saved preferences when present ("all sources
  on by default" now applies only when no preferences are saved); adds the "Reset filters"
  affordance.
- `frontend-events`: topic and distance filters initialize from saved preferences and persist on
  change.
- `frontend-news`: active category tab, time window, and multi-source-only toggle initialize from
  saved preferences and persist on change.

## Impact

- Frontend only; no API, backend, or schema changes.
- Affected code: `frontend/src/features/timeseries/state.svelte.ts`,
  `frontend/src/features/events/state.svelte.ts`, `frontend/src/features/news/state.svelte.ts`,
  the map `FilterPanel.svelte` (reset affordance), plus a new shared `lib/` preferences module.
- No new dependencies. Behavior for first-time visitors is unchanged.
