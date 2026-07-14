## 1. Viewport persistence in MapView

- [x] 1.1 Import `loadPrefs`, `savePrefs`, and `asNumber` from `lib/prefs.svelte` into `MapView.svelte`, and define the key constant `localdash.map.view`.
- [x] 1.2 Change `DEFAULT_VIEW.zoom` from `11` to `12`.
- [x] 1.3 Add a helper that reads the saved viewport: `loadPrefs("localdash.map.view")`, validate `zoom`/`lat`/`lng` each with `asNumber`, and return `{ center, zoom }` only when all three are finite — otherwise `null` (all-or-nothing).
- [x] 1.4 In `onMount`, use the restored viewport for the initial `setView(...)` when present, else fall back to `DEFAULT_VIEW`.
- [x] 1.5 In `publishViewport()` (fires on init and `moveend` / `zoomend`), additionally `savePrefs("localdash.map.view", { zoom, lat, lng })` alongside the existing `debug.setMapViewport(...)`. Leave `flyTo` and detail-track logic untouched.

## 2. Verify

- [x] 2.1 Rebuild the frontend (`vite build` into `static/`) and bring up Docker (`docker compose up --build`).
- [x] 2.2 First-load check: with `localdash.map.view` absent, the map opens at zoom 12 on the Chattanooga center.
- [x] 2.3 Round-trip check: pan/zoom, reload, confirm the map reopens at the same viewport; confirm `localdash.map.view` holds `{ zoom, lat, lng }`.
- [x] 2.4 Tolerance check: set `localdash.map.view` to invalid JSON and to a record with a non-finite field; confirm both fall back to the default view without error.
- [x] 2.5 Isolation check: pan the map without touching filters, confirm `localdash.map` is NOT written (filters keep all-on default for later-added sources).
