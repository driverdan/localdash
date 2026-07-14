## 1. State model: source-scoped categories

- [x] 1.1 In `state.svelte.ts`, replace the bare-name `categories` set with a source-scoped
  selection keyed by `"source:category"` (helper to build/parse the composite key); update
  `allCategories()`-style defaults to emit scoped keys for every source's categories.
- [x] 1.2 Make `selectedSources` a `$derived` set of sources having at least one selected category
  (remove it as independent state).
- [x] 1.3 Remove the source-membership line from `passesFilters` so a feature passes iff its
  `"source:category"` is selected (confirm `FALLBACK`/unknown-source features still behave per the
  "unknown source falls back gracefully" scenario).
- [x] 1.4 Replace `catColor(cat)` usage with direct `colorFor(source, category)` lookups; remove the
  now-unused loop-over-sources color helper.
- [x] 1.5 Update the constructor to restore saved `categories` as an allowlist intersected with the
  known `"source:category"` set (dropping stale/bare-name entries); default to all scoped keys when
  no prefs are present.
- [x] 1.6 Update `resetFilters` to select all known scoped category keys (which loads every source),
  hide closed, and reset the closed window.
- [x] 1.7 Update `persistPrefs` payload to drop the derived `sources` array and persist `categories`
  as scoped keys (keep `showClosed`/`closedWindow`).

## 2. Fetch/delete semantics

- [x] 2.1 In `api.ts`, add a `toggleCategory(source, category, on)` that adds/removes the scoped key
  and, on the source's first-selected/last-selected transition, calls `fetchSourceInto` / deletes the
  source's features.
- [x] 2.2 Reframe `toggleSource(source, on)` as select-all/clear-all of the source's categories with
  the same fetch-on / delete-off behavior (parent on fetches; parent off deletes features).
- [x] 2.3 Ensure `loadActive` iterates the derived `selectedSources` set.

## 3. Filter panel UI

- [x] 3.1 In `FilterPanel.svelte`, replace the two flat `#each` lists with a single nested tree:
  iterate every source in `SOURCES`, render a parent row per source with its categories as indented
  child rows (each child showing its color dot and label).
- [x] 3.2 Wire each child checkbox to `toggleCategory` and read its checked state from the scoped
  selection.
- [x] 3.3 Give each parent row a tri-state checkbox: `checked` when all its categories are selected,
  `indeterminate={...}` when only some are; wire its change handler to `toggleSource` (select/clear
  all).
- [x] 3.4 Add panel styling for the nested indentation and parent/child hierarchy consistent with the
  existing filter panel look.

## 4. Verify

- [x] 4.1 `docker compose up --build` and confirm categories render grouped under their source with
  correct color dots.
- [x] 4.2 Verify tri-state: unchecking one category makes the parent indeterminate; unchecking the
  last unloads the source; parent toggle selects/clears all and fetches/deletes accordingly.
- [x] 4.3 Verify persistence: toggle some categories, reload, selection restores; "Reset filters"
  re-checks everything and removes `localdash.map`; a pre-existing bare-name `localdash.map` falls
  back cleanly to all-on.
- [x] 4.4 Run the frontend lint/format/type checks (pre-commit) and fix any issues.
