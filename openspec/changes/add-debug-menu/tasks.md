## 1. Debug store

- [ ] 1.1 Add `frontend/src/lib/debug.svelte.ts`: a singleton reactive store (mirroring the `ts`
  pattern) with `open` (modal visibility) and a `map` viewport slice `{ zoom, lat, lng }` (nullable
  until seeded), plus a helper to set/clear the map slice
- [ ] 1.2 Export the store from `lib/` so both `MapView` and the shell panel can import it without a
  cross-feature dependency

## 2. Shell debug panel component

- [ ] 2.1 Add a shell component under `frontend/src/lib/` (e.g. `DebugPanel.svelte`) rendering the
  π-glyph toggle button always, and the modal when `debug.open`
- [ ] 2.2 Make the modal route-aware: on `/map` render the map section (zoom + center from the
  store); on other routes render a neutral "no debug data for this view" placeholder
- [ ] 2.3 Add a close control and make the π button toggle `debug.open`
- [ ] 2.4 Mount the component once in `App.svelte`, outside the route `{#if}` chain, so it appears on
  every route

## 3. Map viewport bridge

- [ ] 3.1 In `MapView.svelte`, on map init/`load` and on `moveend` / `zoomend`, write
  `{ zoom: map.getZoom(), center: map.getCenter() }` into the debug store
- [ ] 3.2 Clear the store's map slice on `MapView` teardown so a stale viewport isn't shown after
  leaving `/map`

## 4. Styling

- [ ] 4.1 Style the π button: small round black button, desktop `position: fixed` bottom-right with a
  `z-index` above the map controls
- [ ] 4.2 Add a mobile `@media` breakpoint switching the button to sit at the bottom of the page
- [ ] 4.3 Style the modal: anchored top-right of the main body, offset from `.detail`
  (`top:60px; right:16px; width:360px`) so both can be open without overlap; keep it narrower than
  the detail panel
- [ ] 4.4 Add dark-theme variants (alongside the existing `theme-dark.css` overrides) so the button
  and modal are visible in both themes

## 5. Verify

- [ ] 5.1 `npm run check` passes with zero type errors
- [ ] 5.2 Manually verify: π button on every route; modal opens top-right and coexists with an open
  incident detail panel; `/map` shows live zoom/center that updates on pan/zoom; non-map routes show
  the placeholder; both themes render the button/modal; mobile width moves the button to the bottom
- [ ] 5.3 Rebuild the Docker image (`docker compose up --build`) and confirm the built bundle serves
  the debug overlay
