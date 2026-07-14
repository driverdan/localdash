## Context

The timeseries map filter panel (`FilterPanel.svelte`) renders two independent flat checkbox lists:
**Sources** and **Category**. The category list is `ts.selectedCategoryList` — a de-duplicated union
of the selected sources' categories, keyed by bare name in a `SvelteSet<string>` (`ts.categories`).
Filtering (`passesFilters`) AND-s a source-membership check against a bare-name category check, which
permits a contradictory state (source checked but all its categories unchecked → source shows
nothing) and silently collapses any two sources that share a category name into one toggle/color.

Today two pieces of state carry filter intent: `selectedSources` (also drives fetch/delete via
`api.ts` `toggleSource`) and `categories` (pure display filter). Persistence (`localdash.map`) stores
both as arrays; the constructor treats saved lists as an allowlist intersected with known keys.

Both interaction decisions for this change are already settled (see proposal): the source row is the
**parent** of its categories (tri-state), and category identity becomes **source-scoped**.

## Goals / Non-Goals

**Goals:**
- Render one nested source→category tree so every category sits visibly under its owning source.
- Make the source row a tri-state parent that also drives fetch/delete.
- Scope category identity to its source so names can safely collide.
- Reduce two overlapping state concepts to a single source of truth.

**Non-Goals:**
- No backend, API, schema, or dependency changes.
- No collapsible/expandable source sections (can layer on later if source count grows).
- No change to status/jurisdiction dropdowns, search, show-closed, the table, or marker rendering.
- No localStorage migration code — old saved entries are simply dropped.

## Decisions

**1. Single source of truth: a source-scoped category set.**
Replace `categories: SvelteSet<string>` (bare names) with a set of `"source:category"` keys. Derive
everything else from it:
- `selectedSources` becomes `$derived`: `{ src | some "src:cat" selected }`.
- `passesFilters` drops the source-membership line — an unchecked category already excludes the
  feature, and a source with zero selected categories has all its features excluded implicitly.
- `catColor(cat)`'s "loop selected sources for a color" is replaced by direct
  `colorFor(source, category)` at each render site, which always knows the owning source.

*Alternative considered:* keep `selectedSources` as independent state (source = "loaded", category =
"display filter"). Rejected — the user chose the unified parent model, and keeping both reintroduces
the contradictory state and duplicate persistence this change is meant to remove.

**2. Loaded-ness is derived from category selection; fetch/delete keys on first/last.**
`loadActive` iterates the derived `selectedSources`. `toggleSource`/`toggleCategory` in `api.ts`
become:
- category on → add key; if it's the source's **first** selected category, `fetchSourceInto(src)`.
- category off → delete key; if it was the source's **last**, delete that source's features.
- parent on → add all of the source's category keys; `fetchSourceInto(src)`.
- parent off → delete all of the source's category keys; delete that source's features.

This preserves today's fetch-on / delete-off semantics, re-expressed via first/last category.

*Alternative considered:* never delete features on last-uncheck, just filter them out. Rejected —
leaves stale data in memory and mismatches "parent unchecked = not loaded"; deleting matches current
behavior and keeps memory tidy at the cost of a refetch on re-check (cheap, explicit user action).

**3. Tri-state parent via the `indeterminate` DOM property.**
Parent `checked` = all children selected; `indeterminate` = some-but-not-all. In Svelte 5 the
`<input type="checkbox">` `indeterminate` is a DOM property (not an attribute), set with
`indeterminate={...}` (or `bind:indeterminate`). The parent's `checked` binding drives the
select-all/clear-all action; `indeterminate` is presentational only.

**4. Render order iterates all sources, not just selected ones.**
The tree lists every entry in `SOURCES` (stable declaration order) with its `categories`, so
unloaded sources still show as unchecked parents the user can turn on. Replaces the
`selectedCategoryList` union entirely.

**5. Persistence: drop `sources`, store scoped `categories`.**
`persistPrefs` writes only `categories: string[]` of `"source:cat"` keys (plus the unchanged
`showClosed`/`closedWindow`). The constructor validates saved keys against the known
`"source:category"` set and drops the rest; `resetFilters` selects all known keys. `selectedSources`
is never persisted since it is derived.

## Risks / Trade-offs

- **Existing users lose their saved category selection once.** Old `localdash.map` stores bare names
  (and a `sources` array); none match a scoped key, so selections reset to the all-on default on
  first load. → Acceptable: localStorage-only, one-time, non-destructive (defaults are sensible);
  documented in the proposal. No migration code needed.
- **Re-checking a source's first category refetches its data.** → Only on explicit user toggle;
  per-source fetch is cheap and already how `toggleSource` behaves today.
- **`indeterminate` is easy to get wrong in Svelte** (attribute vs. property, not reset on re-render).
  → Bind it explicitly and derive it from the same category set as `checked`; cover with the
  "parent checkbox reflects child selection" scenario.
- **Removing the source-membership check from `passesFilters` could hide features if a category is
  missing from config.** → The existing `FALLBACK` config yields no categories, so unknown-source
  features would be filtered out; this already effectively happens via the union. Confirm the
  fallback path during implementation and keep the "unknown source falls back gracefully" scenario
  green.

## Migration Plan

Pure frontend rebuild (`docker compose up --build`). No DB migration, no rollback coordination. To
roll back, revert the frontend commit; users' `localdash.map` will again be re-derived from whatever
is present (older builds already tolerate unknown/missing keys).
