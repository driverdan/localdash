## Context

The frontend is a Svelte 5 + Vite SPA. `App.svelte` is the shell: it renders the header (nav, theme
switcher, timeseries status bar) and the route body (`/` news, `/map` timeseries, `/events`). The
Leaflet map instance in `MapView.svelte` is a **component-local variable** (`let map: L.Map`) — no
code outside that component can read its zoom or center today. Shared reactive state uses a
singleton class pattern (`ts` in `features/timeseries/state.svelte.ts`), and `MapView` already
bridges out of Leaflet via reactive state (e.g. `ts.flyToRequest`).

Two placement constraints already exist on the `/map` route: the incident **detail panel** is
`position: fixed; top: 60px; right: 16px; width: 360px` (timeseries.css), and the map itself owns a
`bottomright` EPB legend control plus Leaflet's attribution. `#layout` is a hard flex with a fixed
340px sidebar and **no mobile media query** — there is no existing responsive layout to extend.

## Goals / Non-Goals

**Goals:**
- A shell-owned debug overlay available on every route without coupling to any feature.
- Read live map zoom/center in-app, updating as the map moves.
- A general structure (store + route-aware sections) that new debug sections can join without
  touching existing ones.
- Coexist visually with the incident detail panel; theme-aware in default and dark themes.

**Non-Goals:**
- Any debug section other than the map section (WebSocket state, feature counts, build info, etc.
  are future work — the store and layout just leave room for them).
- Editing/mutating app state from the panel; it is read-only inspection.
- A general responsive redesign of `#layout` — this change adds only the breakpoint the button needs.
- Backend/API changes.

## Decisions

### Debug store lives in `lib/`, not in a feature
A singleton reactive class `frontend/src/lib/debug.svelte.ts` (mirroring the `ts` pattern) holds
`open` (modal visibility) and a `map` viewport slice `{ zoom, lat, lng }`. Because it lives in `lib/`
(shell code), `MapView` may write to it and the shell panel may read it **without a cross-feature
import** — the frontend-shell isolation rule forbids feature→feature imports but allows feature→`lib`
and shell→`lib`. Alternative considered: a Svelte context or event bus — rejected as heavier than the
established singleton-store convention already used across the app.

### Map → store bridge via Leaflet events
`MapView` registers `map.on("moveend zoomend", …)` and sets the store on `load` (and in the `onMount`
init path), writing `{ zoom: map.getZoom(), center: map.getCenter() }`. This mirrors how the map
already bridges to/from reactive state. `moveend` covers pans; `zoomend` covers zoom; `load`/init
seeds the first value. On the map component's teardown the map slice is cleared so a stale viewport
isn't shown after leaving `/map`.

### Shell component composes route-aware sections
A shell component (under `frontend/src/lib/`, e.g. `DebugPanel.svelte`) renders the π button always
and the modal when `debug.open`. Inside the modal it switches on `currentPath()`: `/map` → a map
section reading the store's viewport; other routes → a neutral placeholder. Sections are just
conditional blocks keyed on route, so adding one later is additive. Mounted once in `App.svelte`,
outside the route `{#if}` chain, so it rides above every route.

### Placement: offset the modal, layer the button
- **Modal**: anchored top-right of the main body but offset from `.detail` (which occupies
  `top:60px; right:16px`). Concretely, give the debug modal a different anchor (e.g. a lower `top`
  or a `right` that clears the 360px detail panel) and a `z-index` in the same band as `.detail`
  (1000) so both can be open without overlap.
- **Button**: `position: fixed; bottom/right` on desktop with a `z-index` above the map controls so
  it is clickable even where it visually nears the `bottomright` legend. A `@media (max-width: …)`
  breakpoint switches it to sit at the bottom of the page on mobile.

### π rendered as the glyph
The button content is the literal `π` character in a styled black, round button — no new icon asset.
Reads unambiguously as "pi" and avoids adding a registry entry. Theme-awareness handled with a
dark-theme override alongside the existing `theme-dark.css` overrides.

## Risks / Trade-offs

- **Button overlaps the EPB legend / attribution on `/map`** → place it with adequate offset and a
  higher `z-index`; accept minor visual proximity, since the legend is bottom-*inside* the map and
  the button is bottom-right of the screen.
- **Mobile breakpoint is newly defined** (no existing responsive layout) → scope the media query
  narrowly to the debug button/modal so it doesn't imply a broader `#layout` responsive contract.
- **Stale viewport after leaving `/map`** → clear the store's map slice on `MapView` teardown; the
  panel only renders the map section on the `/map` route anyway.
- **Chosen offset could still crowd the detail panel on narrow desktop widths** → keep the debug
  modal narrower than `.detail` and verify both-open layout during implementation.

## Open Questions

- Exact numeric offset/anchor for the modal and the mobile breakpoint value — settle during
  implementation against the real layout rather than guessing pixel values here.
- Coordinate precision/format for the displayed center (e.g. fixed decimal places) — a small
  presentation choice deferred to implementation.
