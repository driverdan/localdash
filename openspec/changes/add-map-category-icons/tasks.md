## 1. Global icon module

- [x] 1.1 Add Lucide as a bundled dependency in `frontend/package.json` (no CDN) and install
- [x] 1.2 Create `frontend/src/lib/icons/registry.ts` mapping stable icon names to imported Lucide icon data, importing only the icons used so the rest tree-shake out
- [x] 1.3 Create `frontend/src/lib/icons/iconSvg.ts` (or `index.ts`) exposing `iconSvg(name, { size, color, strokeWidth })` that returns an SVG string with `currentColor`/stroke tinted to `color`
- [x] 1.4 Create `frontend/src/lib/icons/Icon.svelte` wrapping `iconSvg` via `{@html}`, accepting `name`, `color`, and `size` props
- [x] 1.5 Add a barrel export so features import from `src/lib/icons`

## 2. Category → icon mapping

- [x] 2.1 Add a per-category `icon` field to each source in `frontend/src/features/timeseries/sources.ts`: `police=siren`, `fire=flame`, `ems=ambulance`, `other=circle-question-mark`, `incident=triangle-alert`, `construction=traffic-cone`, `special_event=party-popper`, `severe=octagon-alert`, `energy=zap`, `fiber=cable`
- [x] 2.2 Add a generic fallback icon for a category with no configured icon (and for `FALLBACK`)
- [x] 2.3 Add an `iconFor(source, category)` helper (alongside `colorFor`/`featureColor`) resolving a feature's icon name

## 3. Map markers

- [x] 3.1 Rewrite `markerIcon()` in `MapView.svelte` to build the `divIcon` from `iconSvg(iconFor(...), { color: featureColor(f), size })` — no teardrop, no dot
- [x] 3.2 Apply EPB's `markerSize` (customers-affected bucket) to the glyph size; center the icon anchor and popup anchor accordingly
- [x] 3.3 Apply reduced opacity for closed entities (drop the dashed-border styling)

## 4. Styling

- [x] 4.1 Add a white halo to map glyphs (drop-shadow/outline) legible on light and dark basemaps in `frontend/src/styles/timeseries.css`
- [x] 4.2 Remove the now-unused `.marker-pin` and `.marker-dot` rules after confirming nothing else references them
- [x] 4.3 Keep the EPB outage-status legend unchanged

## 5. Filter panel glyphs

- [x] 5.1 Replace the category color `.dot` in `FilterPanel.svelte` with the category glyph via the `Icon` component
- [x] 5.2 Tint each category glyph its category color, except EPB categories which render black
- [x] 5.3 Adjust filter-row CSS so the glyph aligns with the label like the old dot did

## 6. Verify

- [x] 6.1 `npm run check` and `npm run build` pass in `frontend/`
- [x] 6.2 Rebuild the app (`docker compose up --build`) and confirm each category renders its glyph on the map, tinted correctly, with halo; EPB glyphs are status-colored and customer-sized; closed entities are muted
- [x] 6.3 Confirm the filter list shows each category glyph (category-tinted, EPB black) and toggling still filters map and table
