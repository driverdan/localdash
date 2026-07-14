## Why

The map filter panel shows Sources and Categories as two disconnected flat lists. The category
list is a de-duplicated union of every selected source's categories, so nothing tells the user
that Police/Fire/EMS belong to Hamilton County 911 while Energy/Fiber belong to EPB. As more
sources are added this only gets more confusing, and the flat bare-name model silently collapses
any two sources that ever share a category name into one shared toggle.

## What Changes

- Replace the two flat lists (Sources, Category) with a **single nested tree**: each source is a
  parent row whose categories are indented children under it.
- Make the source row a **tri-state parent checkbox**: checked when all its categories are on,
  indeterminate when only some are on, unchecked when none are on. Toggling the parent on checks
  all its categories and fetches the source; toggling it off unchecks all its categories and
  removes the source's data.
- **BREAKING (internal state model):** category identity becomes **source-scoped** (`source:category`)
  instead of a bare name shared across sources. Filtering, color lookup, and persistence all key on
  the scoped identity, so two sources may safely define the same category name.
- Collapse the redundant "source on but all its categories off" state: a source is considered loaded
  **iff at least one of its categories is checked**. The separate source-selection set becomes
  derived from the category selection; the source-membership check drops out of `passesFilters`
  because an unchecked category already excludes the feature.
- Toggling a category on fetches its source when it is the source's **first** checked category;
  toggling a category off removes the source's data when it was the source's **last** checked one.
- Update persisted preferences (`localdash.map`): drop the now-derived `sources` array and store
  `categories` as source-scoped keys. Saved bare-name entries no longer match a known scoped key
  and are dropped, falling back cleanly to the all-on default (localStorage only, no migration code).

## Capabilities

### New Capabilities
<!-- None. This reorganizes existing filtering behavior. -->

### Modified Capabilities
- `frontend-timeseries`: the **Filtering** requirement changes from two flat lists keyed by bare
  category names to a nested source→category tree with tri-state parents and source-scoped category
  identity; the **Reset filters to dynamic defaults** requirement changes to reflect the derived
  source-loaded semantics and the new persisted shape.

## Impact

- Frontend only; no backend, API, schema, or dependency changes.
- `frontend/src/features/timeseries/state.svelte.ts` — category set becomes source-scoped keys;
  `selectedSources` becomes `$derived`; `passesFilters` drops the source-membership check; `catColor`
  simplified/removed; prefs read/write and `resetFilters` updated.
- `frontend/src/features/timeseries/api.ts` — `toggleSource` reframed as category toggles with
  first/last fetch-and-delete semantics; `loadActive` fetches the derived loaded-source set.
- `frontend/src/features/timeseries/sources.ts` — grouped-render helper as needed; color lookup via
  `colorFor(source, category)`.
- `frontend/src/features/timeseries/components/FilterPanel.svelte` — nested tree UI with tri-state
  parent checkboxes replacing the two flat `#each` lists.
- Existing users' saved `localdash.map` category selections reset to the all-on default on first load
  after the change (one-time, localStorage only).
