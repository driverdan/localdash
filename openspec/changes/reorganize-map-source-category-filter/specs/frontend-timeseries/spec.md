## MODIFIED Requirements

### Requirement: Filtering
The UI SHALL filter the visible set (map and table together) by: a nested source→category tree,
status and jurisdiction dropdowns (options derived from the currently loaded data), and
case-insensitive text search over title, location, and status. A dropdown selection whose value
disappears from the data SHALL be cleared automatically so UI state and filter state never diverge.

The source→category tree SHALL render every known source as a parent row with its categories as
indented child rows. Category identity SHALL be **source-scoped** (`source:category`), so two sources
may define the same category name without sharing a toggle, and each category's color dot SHALL come
from its own source's config. A parent source row SHALL render a tri-state checkbox: checked when all
of its categories are selected, indeterminate when only some are, and unchecked when none are.

A feature SHALL be visible only if its own `source:category` is selected; a source is considered
loaded **iff at least one of its categories is selected**, so no separate source-membership check is
applied. Interactions SHALL behave as follows:
- Toggling a **category on** selects it and, when it is the first selected category of its source,
  fetches that source's entities.
- Toggling a **category off** deselects it and, when it was the last selected category of its source,
  removes that source's entities from the map and table.
- Toggling a **parent source on** selects all of its categories and fetches that source's entities.
- Toggling a **parent source off** deselects all of its categories and removes that source's entities.

Category selections SHALL initialize from saved preferences (`localdash.map`) when present, otherwise
to all categories of all sources. Saved selections are an explicit allowlist: the saved source-scoped
keys SHALL be intersected with currently-known `source:category` pairs (stale entries dropped), and
sources or categories introduced after the preferences were saved SHALL initialize unselected. With
no saved preferences, all categories SHALL be on by default, including newly introduced ones. Any
category or source toggle SHALL persist the new selection.

#### Scenario: Categories are grouped under their source
- **WHEN** the filter panel renders
- **THEN** each source appears as a parent row with its own categories listed as indented children,
  and each category's color dot matches that source's config

#### Scenario: Parent checkbox reflects child selection
- **WHEN** some but not all of a source's categories are selected
- **THEN** that source's parent checkbox shows the indeterminate state, becoming fully checked when
  every child is selected and unchecked when none are

#### Scenario: Disabling a source removes its footprint
- **WHEN** the user unchecks a source's parent row
- **THEN** all of its categories deselect and its entities leave the map and table, while other
  sources' categories are unaffected

#### Scenario: Unchecking the last category unloads the source
- **WHEN** the user unchecks the only remaining selected category of a source
- **THEN** the source's entities leave the map and table and its parent row becomes unchecked

#### Scenario: Same category name in two sources toggles independently
- **WHEN** two sources each define a category with the same name and the user toggles it under one
  source
- **THEN** only that source's category changes; the identically named category under the other source
  is unaffected

#### Scenario: Stale dropdown selection is reconciled
- **WHEN** the selected status value no longer exists in the loaded data (e.g. "Closed" after hiding
  closed entities)
- **THEN** the filter resets to "All" and the dropdown displays "All"

#### Scenario: Search narrows results
- **WHEN** the user types text into the search box
- **THEN** only entities whose title, location, or status contains the text (case-insensitive)
  remain visible

#### Scenario: First visit defaults everything on
- **WHEN** the page loads with no `localdash.map` key in localStorage
- **THEN** every source's parent row and every category is checked

#### Scenario: Saved selections restore as an allowlist
- **WHEN** the user deselects some categories, reloads, and a new source has since been added to the
  app
- **THEN** the previously-selected categories restore checked, the deselected ones stay unchecked,
  and the new source's categories initialize unchecked

#### Scenario: Stale saved entries are dropped
- **WHEN** `localdash.map` names a `source:category` key that no longer exists in the client config
  (including old bare-name entries from before this change)
- **THEN** the unknown key is ignored and the remaining saved selections apply

### Requirement: Reset filters to dynamic defaults
The filter panel SHALL offer a "Reset filters" control that removes the `localdash.map` stored
preferences and restores the in-memory defaults (all categories of all sources selected — which
loads every source — closed entities hidden, default closed window). After a reset, the browser SHALL
behave as if it had no saved preferences — in particular, sources added later default to selected —
until the user next changes a persisted filter.

#### Scenario: Reset clears stored preferences
- **WHEN** the user has saved preferences and clicks "Reset filters"
- **THEN** every source and category becomes checked, show-closed turns off, and `localdash.map` is
  absent from localStorage (not re-saved with default values)

#### Scenario: Reset restores dynamic defaults for future sources
- **WHEN** the user clicks "Reset filters", reloads, and a new source has since been added
- **THEN** the new source's parent row and all its categories initialize checked
