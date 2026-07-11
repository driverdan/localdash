# frontend-timeseries Specification

## Purpose

The timeseries dashboard UI (`frontend/src/features/timeseries/`, consuming `/api/v1/timeseries/*`):
the Leaflet map with per-source marker styling and coincident-point clustering, the filter panel,
the incident table, the detail panel with observation track, and live WebSocket diff application.
The frontend counterpart of the `timeseries` spec. This feature owns the map until a second feature
needs it.

## Requirements
### Requirement: Per-source display configuration
The timeseries feature SHALL keep all source-specific display knowledge (source names, categories,
category colors, title/location/jurisdiction accessors, detail rows, and marker style overrides) in
one typed module (`features/timeseries/sources.ts`) covering `hc911`, `tdot`, and `epb`, with a
fallback config for unknown source keys. All rendering SHALL resolve config per-feature from the
feature's own `source` property, so multiple sources display simultaneously.

#### Scenario: Unknown source falls back gracefully
- **WHEN** a feature arrives whose `source` key has no client config
- **THEN** it renders with the fallback config (generic title, gray color) rather than erroring

### Requirement: Map rendering
The map SHALL render each visible entity as a Leaflet marker: a teardrop `divIcon` pin colored by
the source's category color by default; for sources with style overrides (EPB), a round dot colored
by outage status and sized by customers affected. Closed entities SHALL render with the muted
"closed" styling. Markers SHALL cluster only when coincident (cluster radius 1px, spiderfiable), and
the map SHALL show the EPB outage-status legend. Clicking a marker SHALL show its popup (title,
source short-name, status, jurisdiction, location) and open the detail panel.

#### Scenario: Category-colored pin for a 911 incident
- **WHEN** an active `hc911` fire incident is visible
- **THEN** its marker is a teardrop pin in the fire category color

#### Scenario: Status-colored sized dot for an EPB outage
- **WHEN** an active `epb` outage with `REPAIR_IN_PROGRESS` status and a large `customer_quantity`
  is visible
- **THEN** its marker is a round dot in the repair-in-progress blue, sized by the customers-affected
  bucket

#### Scenario: Only coincident markers cluster
- **WHEN** two entities share identical coordinates and two others are merely nearby
- **THEN** the coincident pair clusters (and can be spiderfied) while the nearby pair renders as two
  separate markers

### Requirement: Filtering
The UI SHALL filter the visible set (map and table together) by: source checkboxes (all sources on
by default; toggling a source on fetches its entities and enables its categories), category
checkboxes (union of the selected sources' categories, deduplicated), status and jurisdiction
dropdowns (options derived from the currently loaded data), and case-insensitive text search over
title, location, and status. A dropdown selection whose value disappears from the data SHALL be
cleared automatically so UI state and filter state never diverge.

#### Scenario: Disabling a source removes its footprint
- **WHEN** the user unchecks a source
- **THEN** its entities leave the map and table, and categories no other selected source defines
  disappear from the category filter

#### Scenario: Stale dropdown selection is reconciled
- **WHEN** the selected status value no longer exists in the loaded data (e.g. "Closed" after hiding
  closed entities)
- **THEN** the filter resets to "All" and the dropdown displays "All"

#### Scenario: Search narrows results
- **WHEN** the user types text into the search box
- **THEN** only entities whose title, location, or status contains the text (case-insensitive)
  remain visible

### Requirement: Recently-closed visibility
The UI SHALL hide closed entities by default. A "show recently closed" toggle with a window selector
(30 min / 1 h / 3 h / 12 h) SHALL refetch entities with `closed_within=<minutes>` and render closed
entities in muted styling with a "Closed" badge. Turning the toggle off SHALL drop closed entities.

#### Scenario: Enabling show-closed pulls in recent closures
- **WHEN** the user enables "show recently closed" with the 1-hour window
- **THEN** the UI refetches with `closed_within=60` and closed entities appear muted with a "Closed"
  badge in map and table

### Requirement: Incident table
The sidebar SHALL show all currently visible entities in a table (source, category with color dot,
status, type, location) sorted by `last_seen_at` descending, with a live count. Clicking a row SHALL
open the entity's detail panel and fly the map to its position.

#### Scenario: Row click focuses the entity
- **WHEN** the user clicks a table row for an entity with a position
- **THEN** the detail panel opens for that entity and the map flies to its coordinates

### Requirement: Detail panel with observation track
Opening an entity's detail SHALL fetch its snapshot (`/entities/{id}`) and its track
(`/entities/{id}/track`) concurrently, render the source-specific detail rows (empty values
omitted), and list the observation history newest-first with timestamp and status. Track points with
positions SHALL draw on the map as circle markers joined by a dashed polyline when the track has
more than one point; closing the panel SHALL clear the track from the map.

#### Scenario: Detail shows history and draws the track
- **WHEN** the user opens an entity that has moved across several observations
- **THEN** the panel lists its observations newest-first and the map shows the track points joined
  by a dashed line

#### Scenario: Closing the panel clears the track
- **WHEN** the user closes the detail panel
- **THEN** the track polyline and points are removed from the map

### Requirement: Live updates over WebSocket
The feature SHALL connect to `/api/v1/timeseries/ws` (unfiltered) and apply each diff incrementally:
`new` and `updated` features upsert into state, `closed` ids either disappear (default) or flip to
muted closed styling (when show-closed is on); diffs from unselected sources are ignored. A
connection indicator SHALL show "live" while connected and an error state while disconnected, and
the client SHALL reconnect automatically 3 seconds after a close. Applying a diff SHALL NOT require
refetching or re-rendering unaffected entities.

#### Scenario: Diff applies incrementally
- **WHEN** a poll cycle produces a diff with one new and one closed entity
- **THEN** the new entity's marker and row appear and the closed entity disappears (or turns muted
  when show-closed is on), without a full reload

#### Scenario: Muted source diffs are ignored
- **WHEN** a diff arrives for a source the user has unchecked
- **THEN** the UI state does not change

#### Scenario: Reconnect after disconnect
- **WHEN** the WebSocket closes unexpectedly
- **THEN** the indicator shows the disconnected state and a reconnect attempt starts after ~3 seconds,
  restoring "live" on success

### Requirement: Behavioral parity with the replaced UI
The Svelte implementation SHALL be a straight port of the vanilla-JS dashboard: no feature of the
replaced UI is removed and no new user-facing behavior is added in this change.

#### Scenario: Side-by-side equivalence
- **WHEN** the old and new frontends are pointed at the same backend and exercised with the same
  filters and interactions
- **THEN** the same entities are visible with the same styling, table ordering, popup/detail
  content, and live-update behavior

