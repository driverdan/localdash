## 1. Default basemap (backend + config)

- [x] 1.1 In `app/config.py`, set `tile_url` to `https://tile.openstreetmap.org/{z}/{x}/{y}.png` and `tile_attribution` to the OSM contributors attribution (linked to openstreetmap.org/copyright); update the comment above it (drop the CARTO rationale, note OSM tile usage policy and that the dark theme inverts these tiles)
- [x] 1.2 In `.env.example`, replace the Esri `TILE_URL` / `TILE_ATTRIBUTION` with the same OSM values, and note that the dark theme darkens the configured tiles with a CSS filter
- [x] 1.3 Check the README `TILE_URL` / `TILE_ATTRIBUTION` bullet and add a short note if it names a provider or should mention the dark-theme filter
- [x] 1.4 Add an assertion to `tests/test_api_routes.py` (or the config test) that the default `tile_url` points at `tile.openstreetmap.org` and contains no `cartocdn`; run the backend tests

## 2. Dark theme basemap (frontend)

- [x] 2.1 In `frontend/src/lib/theme.svelte.ts`, remove the CARTO `tileUrl` / `tileAttribution` from the `dark` entry; keep the optional fields on the `Theme` interface and update the comment to say the override is optional and the dark theme darkens the configured tiles in CSS instead
- [x] 2.2 In `frontend/src/styles/theme-dark.css`, add a `[data-theme="dark"] .leaflet-tile-pane` filter rule (invert + 180° hue-rotate + brightness/contrast softening) and mention it in the file's header comment
- [x] 2.3 Confirm `MapView.svelte` needs no change (override-or-config fallback still correct); adjust its basemap comment only if it now misdescribes the dark theme
- [x] 2.4 Grep the repo for leftover `cartocdn` / `CARTO` references and remove them
- [x] 2.5 Run frontend checks (`svelte-check` / build) and lint

## 3. Verification

- [x] 3.1 Rebuild and start the stack (`sg docker -c 'docker compose up --build -d'`) and confirm `GET /api/v1/config` returns the OSM `tile_url`
- [x] 3.2 Visually check the map in the light theme: OSM tiles load with no watermark, attribution shows OpenStreetMap contributors, and incident markers stay legible
- [x] 3.3 Switch to the dark theme with the map open: the basemap darkens instantly without reload, while markers, polygons, popups, and the attribution control keep their normal colors; tune the filter values if the result is too harsh
