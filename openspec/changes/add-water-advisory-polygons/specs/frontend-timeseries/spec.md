## MODIFIED Requirements

### Requirement: Per-source display configuration
The timeseries feature SHALL keep all source-specific display knowledge (source names, categories,
category colors, title/location/jurisdiction accessors, detail rows, and marker style overrides) in
one typed module (`features/timeseries/sources.ts`) covering `hc911`, `tdot`, `epb`, and `tnaw`
(Tennessee American Water advisories), with a fallback config for unknown source keys. All rendering
SHALL resolve config per-feature from the feature's own `source` property, so multiple sources
display simultaneously.

#### Scenario: Unknown source falls back gracefully
- **WHEN** a feature arrives whose `source` key has no client config
- **THEN** it renders with the fallback config (generic title, gray color) rather than erroring

#### Scenario: Advisory source has display config
- **WHEN** a `tnaw` advisory feature is rendered
- **THEN** it resolves the `tnaw` config for its title (advisory header), category color, and popup fields

### Requirement: Map rendering
The map SHALL render each visible entity according to its geometry type. **Point** entities SHALL
render as a Leaflet marker whose mark is the entity category's **glyph** (a `divIcon` containing the
category's icon), tinted by `featureColor()`: the source's category color by default, or, for sources
with a marker-color override (EPB), the outage-status color. The glyph SHALL carry a subtle white halo
so it remains legible on both light and dark basemaps. For sources with a marker-size override (EPB),
the glyph SHALL be sized by that override (customers affected). Point markers SHALL cluster only when
coincident (cluster radius 1px, spiderfiable). **Polygon / MultiPolygon** entities (e.g. `tnaw`
advisory affected areas) SHALL render as filled, outlined Leaflet areas in a dedicated layer group
that is **not** part of the point marker cluster, styled by the source's category (e.g. emergency vs
general advisory). Closed entities SHALL render with reduced opacity for both markers and polygons.
The map SHALL show the EPB outage-status legend. Clicking either a marker or a polygon SHALL show its
popup (title, source short-name, status, jurisdiction, location) and open the detail panel.

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

#### Scenario: Advisory area rendered as a polygon
- **WHEN** an active `tnaw` advisory with a polygon affected area is visible
- **THEN** it renders as a filled, outlined area styled by its advisory category (not a clustered
  point marker), and clicking it opens its popup and detail panel

#### Scenario: Closed entity is muted
- **WHEN** a visible entity is closed
- **THEN** its glyph or polygon renders at reduced opacity

#### Scenario: Only coincident markers cluster
- **WHEN** two point entities share identical coordinates and two others are merely nearby
- **THEN** the coincident pair clusters (and can be spiderfied) while the nearby pair renders as two
  separate markers, and any polygon entities are unaffected by clustering

### Requirement: Incident table
The sidebar SHALL show all currently visible entities in a table (source, category with color dot,
status, type, location) sorted by `last_seen_at` descending, with a live count. Clicking a row SHALL
open the entity's detail panel and focus the map on the entity: flying to its coordinates for point
entities, or fitting the map to the affected-area bounds for polygon entities.

#### Scenario: Row click focuses a point entity
- **WHEN** the user clicks a table row for a point entity with a position
- **THEN** the detail panel opens for that entity and the map flies to its coordinates

#### Scenario: Row click focuses a polygon entity
- **WHEN** the user clicks a table row for a polygon entity (e.g. a `tnaw` advisory)
- **THEN** the detail panel opens and the map fits the advisory's affected-area bounds

### Requirement: Detail panel with observation track
Opening an entity's detail SHALL fetch its snapshot (`/entities/{id}`) and its track
(`/entities/{id}/track`) concurrently, render the source-specific detail rows (empty values
omitted), and list the observation history newest-first with timestamp and status. For entities whose
track has point geometry, track points with positions SHALL draw on the map as circle markers joined
by a dashed polyline when the track has more than one point; for non-point (polygon) tracks the on-map
track drawing SHALL be a no-op while the textual history list still renders. Closing the panel SHALL
clear any track drawing from the map.

#### Scenario: Detail shows history and draws the track
- **WHEN** the user opens a point entity that has moved across several observations
- **THEN** the panel lists its observations newest-first and the map shows the track points joined
  by a dashed line

#### Scenario: Polygon entity detail lists history without a point track
- **WHEN** the user opens a `tnaw` advisory entity
- **THEN** the panel lists its status history newest-first and no circle-marker/polyline track is drawn

#### Scenario: Closing the panel clears the track
- **WHEN** the user closes the detail panel
- **THEN** the track polyline and points are removed from the map
