# frontend-timeseries Delta

## MODIFIED Requirements

### Requirement: Filtering
The UI SHALL filter the visible set (map and table together) by: source checkboxes, category
checkboxes (union of the selected sources' categories, deduplicated), status and jurisdiction
dropdowns (options derived from the currently loaded data), and case-insensitive text search over
title, location, and status. A dropdown selection whose value disappears from the data SHALL be
cleared automatically so UI state and filter state never diverge.

Source and category selections SHALL initialize from saved preferences (`localdash.map`) when
present, otherwise to all sources and all categories. Saved selections are an explicit allowlist:
the saved lists SHALL be intersected with currently-known source keys and category names (stale
entries dropped), and sources or categories introduced after the preferences were saved SHALL
initialize unchecked. With no saved preferences, all sources and categories SHALL be on by default,
including newly introduced ones. Toggling a source on fetches its entities; toggling a source or
category SHALL persist the new selections.

#### Scenario: Disabling a source removes its footprint
- **WHEN** the user unchecks a source
- **THEN** its entities leave the map and table, and categories no other selected source defines
  disappear from the category filter

#### Scenario: Stale dropdown selection is reconciled
- **WHEN** the selected status value no longer exists in the loaded data (e.g. "Closed" after hiding
  closed entities)
- **THEN** the status filter resets to "all" instead of silently filtering on a stale value

#### Scenario: First visit defaults everything on
- **WHEN** the page loads with no `localdash.map` key in localStorage
- **THEN** every source and every category is checked

#### Scenario: Saved selections restore as an allowlist
- **WHEN** the user unchecks a source, reloads, and a new source has since been added to the app
- **THEN** the previously-selected sources restore checked, the unchecked source stays unchecked,
  and the new source initializes unchecked

#### Scenario: Stale saved entries are dropped
- **WHEN** `localdash.map` names a source key that no longer exists in the client config
- **THEN** the unknown key is ignored and the remaining saved selections apply

### Requirement: Recently-closed visibility
The UI SHALL hide closed entities by default. A "show recently closed" toggle with a window selector
(30 min / 1 h / 3 h / 12 h) SHALL refetch entities with `closed_within=<minutes>` and render closed
entities in muted styling with a "Closed" badge. Turning the toggle off SHALL drop closed entities.
The toggle state and window selection SHALL persist in `localdash.map` and restore on load.

#### Scenario: Enabling show-closed pulls in recent closures
- **WHEN** the user enables "show recently closed" with the 1-hour window
- **THEN** the UI refetches with `closed_within=60` and closed entities appear muted with a "Closed"
  badge in map and table

#### Scenario: Show-closed survives a reload
- **WHEN** the user enables "show recently closed" with the 3-hour window and reloads the page
- **THEN** the toggle restores enabled with the 3-hour window and closed entities are fetched

## ADDED Requirements

### Requirement: Reset filters to dynamic defaults
The filter panel SHALL offer a "Reset filters" control that removes the `localdash.map` stored
preferences and restores the in-memory defaults (all sources and categories selected, closed
entities hidden, default closed window). After a reset, the browser SHALL behave as if it had no
saved preferences — in particular, sources added later default to checked — until the user next
changes a persisted filter.

#### Scenario: Reset clears stored preferences
- **WHEN** the user has saved preferences and clicks "Reset filters"
- **THEN** all sources and categories become checked, show-closed turns off, and `localdash.map` is
  absent from localStorage (not re-saved with default values)

#### Scenario: Reset restores dynamic defaults for future sources
- **WHEN** the user clicks "Reset filters", reloads, and a new source has since been added
- **THEN** the new source initializes checked
