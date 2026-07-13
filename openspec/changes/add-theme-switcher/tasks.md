# Tasks: add-theme-switcher

## 1. Theme registry and application

- [ ] 1.1 Create the theme module `frontend/src/lib/theme.svelte.ts`: a registry of themes
      (`{ id, label, tileUrl?, tileAttribution? }`) with the current look as the default entry, a
      reactive current-theme value for the switcher, and `applyTheme(id)` that sets
      `data-theme` on `document.documentElement` and writes `localStorage['localdash.theme']`
- [ ] 1.2 Wire the global theme stylesheets: each theme's rules scoped under `[data-theme="<id>"]`,
      layered on the `frontend-styling` global sheets; the default theme needs no attribute (base
      styling is the default)

## 2. Pre-paint bootstrap and persistence

- [ ] 2.1 Add a synchronous inline `<script>` in `frontend/index.html` `<head>` that reads
      `localStorage['localdash.theme']` (in a try/catch) and sets `data-theme` on the root before
      the app bundle loads
- [ ] 2.2 Confirm the registry's `applyTheme` writes the same `localdash.theme` key the inline
      script reads, and that an unknown/absent value falls through to default styling

## 3. Switcher UI in the shell

- [ ] 3.1 Add a theme switcher control to the header (feature-agnostic shell), bound to the
      registry's theme list and current selection, calling `applyTheme` on change
- [ ] 3.2 Style the switcher via the global shell stylesheet (no scoped visual styles, per the
      styling contract)

## 4. Alternate (dark) theme

- [ ] 4.1 Author a `[data-theme="dark"]` stylesheet that changes surfaces, typography, and color
      across shell, map (filters/table/detail/legend), news, and events — exercising the semantic
      hooks to prove the contract supports layout/type changes, not just color
- [ ] 4.2 Add the dark theme's basemap override (e.g. Carto `dark_all`) to its registry entry

## 5. Themed basemap in the map

- [ ] 5.1 Update `MapView.svelte` to select the tile layer from the active theme's override when
      present, else the `/api/v1/config` `tile_url`; swap the Leaflet tile layer reactively when the
      theme changes while the map is open

## 6. Verification

- [ ] 6.1 Run `npm run check` in `frontend/` (0 errors) and rebuild via
      `sg docker -c 'docker compose up --build -d'`
- [ ] 6.2 Drive the running app: switch themes from the header and confirm the whole site (all three
      pages) re-styles instantly; confirm the map basemap swaps under the dark theme
- [ ] 6.3 Save the dark theme, reload, and confirm the first painted frame is already dark (no FOUC);
      confirm the choice persists across reloads and that clearing `localdash.theme` returns to
      default
