## Context

The timeseries map (`frontend/src/features/timeseries/`) keeps all source-specific display knowledge in `sources.ts`: per-source category lists, category colors, a `featureColor()` accessor, and style overrides. Markers are built in `MapView.svelte`'s `markerIcon()` as Leaflet `divIcon`s — a CSS teardrop (`.marker-pin`) for hc911/tdot, a round dot (`.marker-dot`) for EPB (colored by repair status, sized by customers affected). The filter panel (`FilterPanel.svelte`) shows a small color `.dot` beside each category label.

Categories carry no glyph today, so color is the only differentiator, and colors collide across sources (`police`/`incident` blue, `fire`/`severe` red). The project bundles all assets (no CDN — see AGENTS.md), builds with plain Vite, and uses Svelte 5 runes. Markers are constructed as **HTML strings** inside `divIcon`, while the filter panel renders **Svelte template** — any icon primitive must serve both.

## Goals / Non-Goals

**Goals:**
- A single global icon module (`src/lib/icons/`) any feature can use, with one registry feeding both an SVG-string helper and a Svelte component.
- Per-category glyphs on the map, tinted by the existing `featureColor()`, legible on light and dark basemaps.
- Glyphs in the filter list, category-tinted, with EPB shown black.
- Preserve EPB's status color and size-by-customers behavior; preserve clustering, popups, legend, and closed-state muting.

**Non-Goals:**
- No backend, API, or data-schema changes.
- Not adopting an icon library beyond what's needed (no theming framework, no icon picker UI).
- Not restyling news/events; the module is merely made available to them.
- Not changing category identity, filter logic, or preferences behavior.

## Decisions

### Decision: Use Lucide as the icon source
Lucide is MIT-licensed, ~1,600 icons on a consistent 24×24 stroke grid, and its icons use `currentColor`, so tinting is a matter of setting `color`/stroke. All ten needed glyphs exist (`siren`, `flame`, `ambulance`, `circle-question-mark`, `triangle-alert`, `traffic-cone`, `party-popper`, `octagon-alert`, `zap`, `cable`).

*Alternatives considered:* **Emoji** — rejected: can't recolor and render inconsistently across OSes. **Iconify** — rejected: fetches from its API by default, conflicting with the no-CDN rule. **Icon fonts** — rejected: no per-icon tree-shaking, poor crispness at marker size.

### Decision: One registry, two render paths
The core primitive is `iconSvg(name, { size, color, strokeWidth })` returning an SVG **string**, consumed directly by the Leaflet `divIcon` HTML. `Icon.svelte` is a thin wrapper that renders the same string via `{@html}` for template contexts. Both read from one registry that maps a stable icon name to its Lucide icon data, so the map and filter panel can never drift.

*Alternatives considered:* importing a per-icon Svelte component set (e.g. `lucide-svelte`) — rejected because it does not give the map an SVG string without extra rendering machinery; a single string helper covers both cases with less surface.

### Decision: Only bundle the icons we use
The registry imports each needed icon by name so the bundler tree-shakes the rest of Lucide out. Adding a new glyph is a one-line registry addition.

### Decision: Glyph replaces the marker shape
Markers become the glyph alone — no teardrop, no dot. The glyph is tinted by `featureColor()` (category color for hc911/tdot, EPB status color for EPB). A per-category `icon` field is added to each source's config in `sources.ts` (its natural home alongside `colors`), with a fallback icon for unknown categories.

### Decision: White halo for contrast; opacity for closed
Removing the pin removes its white border/background, so glyphs get a subtle white halo (drop-shadow / outline) to stay readable on any basemap in both themes. "Closed" styling drops the dashed border and becomes reduced opacity only.

### Decision: EPB size preserved; filter glyphs black for EPB
EPB's `markerSize` (bucketed by `customer_quantity`) now scales the glyph instead of a dot, keeping the "bigger outage = bigger mark" cue. In the filter panel, category glyphs are tinted their category color, but EPB's are rendered black because on the map EPB color encodes repair status, not category — a category tint there would imply a mapping that doesn't exist.

## Risks / Trade-offs

- **Glyph legibility on cluttered tiles** → white halo plus stroke weight tuned for ~20px marks; verified against both light and dark basemaps.
- **Loss of the teardrop's point-anchor semantics** (a pin tip marks the exact coordinate; a centered glyph does not) → accept centered anchoring; at Chattanooga zoom levels the offset is negligible and clustering behavior is unchanged.
- **EPB filter tint (black) differs from its map tint (status color)** → intentional and documented; the alternative (category-tinting EPB in the filter) would misrepresent EPB's status-first color model.
- **Bundle size from Lucide** → mitigated by importing only the ~10 used icons so tree-shaking drops the rest.
- **Existing `.marker-pin`/`.marker-dot` CSS retired** → confirm no other component references them before removal.
