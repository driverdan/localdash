## MODIFIED Requirements

### Requirement: Map rendering
The map SHALL render each visible entity as a Leaflet marker whose mark is the entity category's **glyph** (a `divIcon` containing the category's icon), tinted by `featureColor()`: the source's category color by default, or, for sources with a marker-color override (EPB), the outage-status color. The glyph SHALL carry a subtle white halo so it remains legible on both light and dark basemaps. For sources with a marker-size override (EPB), the glyph SHALL be sized by that override (customers affected). Closed entities SHALL render with reduced opacity. Markers SHALL cluster only when coincident (cluster radius 1px, spiderfiable), and the map SHALL show the EPB outage-status legend. Clicking a marker SHALL show its popup (title, source short-name, status, jurisdiction, location) and open the detail panel.

Each source's config SHALL map every one of its categories to an icon; a category with no configured icon SHALL fall back to a generic icon rather than rendering an empty marker. The category-to-icon assignments SHALL be: `police=siren`, `fire=flame`, `ems=ambulance`, `other=circle-question-mark`, `incident=triangle-alert`, `construction=traffic-cone`, `special_event=party-popper`, `severe=octagon-alert`, `energy=zap`, `fiber=cable`.

#### Scenario: Category glyph for a 911 incident
- **WHEN** an active `hc911` fire incident is visible
- **THEN** its marker is the `flame` glyph tinted the fire category color, with a white halo

#### Scenario: Status-colored sized glyph for an EPB outage
- **WHEN** an active `epb` energy outage with `REPAIR_IN_PROGRESS` status and a large `customer_quantity` is visible
- **THEN** its marker is the `zap` glyph tinted the repair-in-progress blue and enlarged by the customers-affected bucket

#### Scenario: Closed entity is muted
- **WHEN** a visible entity is closed
- **THEN** its glyph renders at reduced opacity

#### Scenario: Only coincident markers cluster
- **WHEN** two entities share identical coordinates and two others are merely nearby
- **THEN** the coincident pair clusters (and can be spiderfied) while the nearby pair renders as two separate markers

### Requirement: Filtering
The UI SHALL filter the visible set (map and table together) by: a nested source→category tree, status and jurisdiction dropdowns (options derived from the currently loaded data), and case-insensitive text search over title, location, and status. A dropdown selection whose value disappears from the data SHALL be cleared automatically so UI state and filter state never diverge.

The source→category tree SHALL render every known source as a parent row with its categories as indented child rows. Category identity SHALL be **source-scoped** (`source:category`), so two sources may define the same category name without sharing a toggle. Each category child row SHALL display that category's **glyph**: tinted the category's color by default, or rendered black for sources whose on-map marker color encodes something other than category (EPB). A parent source row SHALL render a tri-state checkbox: checked when all of its categories are selected, indeterminate when only some are, and unchecked when none are.

A feature SHALL be visible only if its own `source:category` is selected; a source is considered loaded **iff at least one of its categories is selected**, so no separate source-membership check is applied. Interactions SHALL behave as follows:
- Toggling a **category on** selects it and, when it is the first selected category of its source, fetches that source's entities.
- Toggling a **category off** deselects it and, when it was the last selected category of its source, removes that source's entities from the map and table.
- Toggling a **parent source on** selects all of its categories and fetches that source's entities.
- Toggling a **parent source off** deselects all of its categories and removes that source's entities.

Category selections SHALL initialize from saved preferences (`localdash.map`) when present, otherwise to all categories of all sources. Saved selections are an explicit allowlist: the saved source-scoped keys SHALL be intersected with currently-known `source:category` pairs (stale entries dropped), and sources or categories introduced after the preferences were saved SHALL initialize unselected. With no saved preferences, all categories SHALL be on by default, including newly introduced ones. Any category or source toggle SHALL persist the new selection.

#### Scenario: Categories are grouped under their source
- **WHEN** the filter panel renders
- **THEN** each source appears as a parent row with its own categories listed as indented children, and each category row shows that category's glyph

#### Scenario: Category glyph tinting in the filter list
- **WHEN** the filter panel renders an `hc911` category row and an `epb` category row
- **THEN** the `hc911` category glyph is tinted its category color while the `epb` category glyph is rendered black

#### Scenario: Parent checkbox reflects child selection
- **WHEN** some but not all of a source's categories are selected
- **THEN** that source's parent checkbox shows the indeterminate state, becoming fully checked when every child is selected and unchecked when none are

#### Scenario: Disabling a source removes its footprint
- **WHEN** the user unchecks a source's parent row
- **THEN** all of its categories deselect and its entities leave the map and table, while other sources' categories are unaffected

#### Scenario: Unchecking the last category unloads the source
- **WHEN** the user unchecks the only remaining selected category of a source
- **THEN** the source's entities leave the map and table and its parent row becomes unchecked

#### Scenario: Same category name in two sources toggles independently
- **WHEN** two sources each define a category with the same name and the user toggles it under one source
- **THEN** only that source's category changes; the identically named category under the other source is unaffected

#### Scenario: Stale dropdown selection is reconciled
- **WHEN** the selected status value no longer exists in the loaded data (e.g. "Closed" after hiding closed entities)
- **THEN** the filter resets to "All" and the dropdown displays "All"

#### Scenario: Search narrows results
- **WHEN** the user types text into the search box
- **THEN** only entities whose title, location, or status contains the text (case-insensitive) remain visible
