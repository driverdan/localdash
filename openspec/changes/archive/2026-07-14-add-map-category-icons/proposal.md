## Why

Map categories are currently distinguished by color alone, which collapses under real data: `police`/`incident` are both blue and `fire`/`severe` are both red, so two unrelated categories look identical. A unique glyph per category makes each one identifiable at a glance regardless of color, and gives the app a reusable icon primitive it does not have today.

## What Changes

- Add **Lucide** as a bundled dependency and a new global icon module at `src/lib/icons/` (no CDN), exposing both an `iconSvg(name, {...})` string helper (for Leaflet `divIcon` HTML) and an `Icon.svelte` component (for Svelte templates), backed by one shared registry. Usable by any feature, not just the map.
- Assign each timeseries category a Lucide glyph: `police=siren`, `fire=flame`, `ems=ambulance`, `other=circle-question-mark`, `incident=triangle-alert`, `construction=traffic-cone`, `special_event=party-popper`, `severe=octagon-alert`, `energy=zap`, `fiber=cable`.
- **BREAKING (visual):** Map markers become the **glyph itself** — the teardrop pin and the EPB round dot are removed. The glyph is tinted by the existing `featureColor()` (category color, or EPB repair-status color). A subtle white halo keeps glyphs legible on both light and dark basemaps. EPB's size-by-customers-affected encoding is preserved, applied to the glyph size. "Closed" styling becomes reduced opacity only (no more dashed border).
- Show the category glyph in the filter panel next to each category label. Glyphs are tinted their category color, **except** EPB's (`energy`, `zap` / `fiber`, `cable`), which render in black because EPB's on-map color encodes status rather than category.

## Capabilities

### New Capabilities
- `frontend-icons`: A global, bundled icon module providing a shared icon registry and two render paths — an SVG-string helper for imperative/HTML contexts and a Svelte component for templates — with configurable color and size.

### Modified Capabilities
- `frontend-timeseries`: Map marker rendering changes from colored teardrop/dot shapes to per-category glyphs (tinted, haloed, EPB size preserved, closed = opacity), and the filter panel's category color-dot becomes the category glyph (category-tinted, EPB in black).

## Impact

- **Dependencies:** adds Lucide to `frontend/package.json`.
- **New code:** `frontend/src/lib/icons/` (registry + `iconSvg` helper + `Icon.svelte`).
- **Changed code:** `frontend/src/features/timeseries/sources.ts` (per-category icon mapping), `frontend/src/features/timeseries/components/MapView.svelte` (`markerIcon`), `frontend/src/features/timeseries/components/FilterPanel.svelte` (category row), `frontend/src/styles/timeseries.css` (marker/halo/closed styles; `.marker-pin`/`.marker-dot` retired). The EPB outage-status legend is unchanged.
- **No backend, API, or schema changes.**
