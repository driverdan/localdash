## Why

When something looks wrong on the dashboard, there is no in-app way to inspect the live UI state —
you drop to the browser console. A lightweight, always-available debug overlay lets us read runtime
state (starting with the map's zoom and center) directly in the UI, and gives a home for future
diagnostics without cluttering the normal chrome.

## What Changes

- Add a small **π-glyph button** that is present on every route: floating in the bottom-right corner
  on desktop, and pinned to the bottom of the page on mobile (via a new breakpoint, since `#layout`
  has no existing mobile layout). Styled black and theme-aware.
- Clicking the button toggles a **debug modal** anchored to the top-right of the main body, offset
  from the existing incident detail panel so both can be open simultaneously without overlapping.
- The panel is **route-aware**: it renders sections relevant to the current route. On `/map` it
  shows the current **map zoom level** and the **latitude/longitude of the map center**, updating
  live as the user pans and zooms. Routes with no debug section show a neutral placeholder.
- Build the panel as a **general debug shell** — a singleton reactive store in `frontend/src/lib/`
  (mirroring the `ts` store pattern) plus a shell-owned component mounted in `App.svelte` — shipping
  only the map section now so future sections (WebSocket state, feature counts, etc.) can be added
  without rework.
- The timeseries map **publishes its viewport** (zoom + center) to the shell debug store on Leaflet
  `moveend` / `zoomend` / `load`, so the shell panel can read it without a cross-feature import.

## Capabilities

### New Capabilities
- `frontend-debug`: A shell-owned debug overlay — the π toggle button (desktop bottom-right / mobile
  bottom-of-page), the offset top-right modal, its route-aware section rendering, the singleton
  debug store in `lib/`, and the map section (live zoom + center). Theme-aware styling.

### Modified Capabilities
- `frontend-timeseries`: The map view additionally publishes its live viewport (zoom and center
  coordinates) to the shell debug store as the map moves, so the debug overlay can display it.

## Impact

- **New**: `frontend/src/lib/debug.svelte.ts` (store), a shell debug component under
  `frontend/src/lib/`, and `App.svelte` mounting it. New styling (button + modal + mobile
  breakpoint), including a dark-theme variant.
- **Modified**: `frontend/src/features/timeseries/components/MapView.svelte` adds Leaflet event
  handlers that write viewport state into the shell store. No cross-feature imports (the store lives
  in `lib/`, consistent with the frontend-shell isolation rules).
- No backend, API, dependency, or data changes.
