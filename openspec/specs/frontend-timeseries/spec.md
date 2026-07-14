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
The map SHALL render each visible entity as a Leaflet marker whose mark is the entity category's
**glyph** (a `divIcon` containing the category's icon), tinted by `featureColor()`: the source's
category color by default, or, for sources with a marker-color override (EPB), the outage-status
color. The glyph SHALL carry a subtle white halo so it remains legible on both light and dark
basemaps. For sources with a marker-size override (EPB), the glyph SHALL be sized by that override
(customers affected). Closed entities SHALL render with reduced opacity. Markers SHALL cluster only
when coincident (cluster radius 1px, spiderfiable), and the map SHALL show the EPB outage-status
legend. Clicking a marker SHALL show its popup (title, source short-name, status, jurisdiction,
location) and open the detail panel.

Each source's config SHALL map every one of its categories to an icon; a category with no configured
icon SHALL fall back to a generic icon rather than rendering an empty marker. The category-to-icon
assignments SHALL be: `police=siren`, `fire=flame`, `ems=ambulance`, `other=circle-question-mark`,
`incident=triangle-alert`, `construction=traffic-cone`, `special_event=party-popper`,
`severe=octagon-alert`, `energy=zap`, `fiber=cable`.

#### Scenario: Category glyph for a 911 incident
- **WHEN** an active `hc911` fire incident is visible
- **THEN** its marker is the `flame` glyph tinted the fire category color, with a white halo

#### Scenario: Status-colored sized glyph for an EPB outage
- **WHEN** an active `epb` energy outage with `REPAIR_IN_PROGRESS` status and a large
  `customer_quantity` is visible
- **THEN** its marker is the `zap` glyph tinted the repair-in-progress blue and enlarged by the
  customers-affected bucket

#### Scenario: Closed entity is muted
- **WHEN** a visible entity is closed
- **THEN** its glyph renders at reduced opacity

#### Scenario: Only coincident markers cluster
- **WHEN** two entities share identical coordinates and two others are merely nearby
- **THEN** the coincident pair clusters (and can be spiderfied) while the nearby pair renders as two
  separate markers

### Requirement: Filtering
The UI SHALL filter the visible set (map and table together) by: a nested source→category tree,
status and jurisdiction dropdowns (options derived from the currently loaded data), and
case-insensitive text search over title, location, and status. A dropdown selection whose value
disappears from the data SHALL be cleared automatically so UI state and filter state never diverge.

The source→category tree SHALL render every known source as a parent row with its categories as
indented child rows. Category identity SHALL be **source-scoped** (`source:category`), so two sources
may define the same category name without sharing a toggle. Each category child row SHALL display
that category's **glyph**: tinted the category's color by default, or rendered black for sources whose
on-map marker color encodes something other than category (EPB). A parent source row SHALL render a
tri-state checkbox: checked when all of its categories are selected, indeterminate when only some are,
and unchecked when none are.

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
  and each category row shows that category's glyph

#### Scenario: Category glyph tinting in the filter list
- **WHEN** the filter panel renders an `hc911` category row and an `epb` category row
- **THEN** the `hc911` category glyph is tinted its category color while the `epb` category glyph is
  rendered black

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

### Requirement: Themed basemap
The map's Leaflet tile layer SHALL follow the active theme: `MapView` SHALL use the active theme's
basemap tile override when the theme registry declares one, and otherwise the server-configured
`tile_url` from `GET /api/v1/config` (which remains the default theme's basemap). When the theme
changes while the map is open, the tile layer SHALL update to match, so a dark theme does not leave
a bright basemap under a dark shell. The `app-shell` config contract is unchanged.

#### Scenario: Default theme uses the configured basemap
- **WHEN** the default theme is active
- **THEN** the map renders with the `tile_url` basemap from `/api/v1/config`

#### Scenario: Dark theme swaps the basemap
- **WHEN** the user switches to a dark theme that declares a dark tile override while the map is open
- **THEN** the map's tile layer updates to the dark basemap without a page reload

### Requirement: Map viewport published to the debug store
The map view SHALL publish its live viewport — the current zoom level and the center coordinates
(latitude and longitude) — to the shell debug store as the map moves. It SHALL update the store on
Leaflet `load`, `moveend`, and `zoomend` so the published values track pans and zooms. The store
lives in `frontend/src/lib/`, so this SHALL NOT introduce a cross-feature import (consistent with the
frontend-shell isolation rules).

#### Scenario: Viewport published on load
- **WHEN** the map finishes initializing on the `/map` route
- **THEN** the debug store holds the map's initial zoom level and center coordinates

#### Scenario: Viewport tracks map movement
- **WHEN** the user pans or zooms the map
- **THEN** the debug store's zoom and center values are updated to the new viewport on `moveend` /
  `zoomend`

