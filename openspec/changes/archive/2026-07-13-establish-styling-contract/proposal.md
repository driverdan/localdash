# Proposal: establish-styling-contract

## Why

The frontend is split-brained about styling. The map/timeseries feature carries **zero** scoped
`<style>` blocks — all its styling lives in the global `app.css`, targeting semantic hooks
(`#layout`, `#sidebar`, `#map`, `.filters`, `.detail`, `.map-legend`) — which makes it fully
restyleable from an external stylesheet. The news and events features do the opposite: ~234 lines
of Svelte-scoped `<style>` across six components, compiled to opaque `.class.svelte-hash`
selectors that no external stylesheet can reliably target. This inconsistency blocks any
site-wide theming (layout, fonts, or colors) and means there is no single source of visual truth.
This change formalizes the map's proven model as a contract and migrates news/events onto it —
valuable on its own (one consistent styling model), and the prerequisite for `add-theme-switcher`.

## What Changes

- Define a **styling contract** the whole frontend follows:
  - Markup exposes stable, semantic styling hooks — ids for singleton regions, semantic classes
    for repeated elements, element state via classes/`data-*` attributes — and carries **no
    presentational-only wrapper elements** and **no structural inline styles** (data-driven inline
    values like a marker's category color remain fine).
  - Feature components contain **no scoped visual `<style>` blocks**; all visual styling lives in
    global stylesheets organized by feature.
- Migrate the six scoped news/events components (`EventsPage`, `EventCard`, `NewsFeed`,
  `StoryCard`, `CategoryTabs`, `SourcesFooter`) to the contract: lift their styles into global
  feature stylesheets, normalize their markup to semantic hooks, and remove any baked-in layout
  assumptions that would prevent a theme from reflowing them.
- Reorganize the single `app.css` into a maintainable global-stylesheet structure (a base layer
  plus per-feature sheets) as the site's one source of visual truth.
- **Pure refactor: rendered output is unchanged.** No theme is added here — this change only makes
  the substrate themeable.

## Capabilities

### New Capabilities

- `frontend-styling`: the site-wide styling contract — semantic markup hooks, global
  feature-organized stylesheets, no scoped visual styles, assumption-free markup — that makes the
  UI restyleable in layout, typography, and color.

### Modified Capabilities

- `frontend-news`: adds a requirement that the feature styles via the global contract (no scoped
  visual styles; markup exposes semantic hooks). Existing rendering requirements are unchanged.
- `frontend-events`: adds the same styling-contract requirement. Existing rendering requirements
  are unchanged.

## Impact

- Frontend only; no API, backend, or behavioral changes. Rendered pixels are held constant.
- Affected code: the six news/events components lose their `<style>` blocks; `frontend/src/app.css`
  is reorganized into base + per-feature global stylesheets; news/events markup gains/normalizes
  semantic class and id hooks.
- No new dependencies. The map/timeseries feature already conforms and is largely untouched beyond
  documenting its pattern as the reference.
- Unblocks `add-theme-switcher`, which layers themes on top of this contract.
