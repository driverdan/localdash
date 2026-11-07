## MODIFIED Requirements

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
`severe=octagon-alert`, `energy=zap`, `fiber=cable`, and for `tnaw` advisories
`emergency=octagon-alert`, `general=droplet`. The generic fallback icon SHALL be `map-pin`.

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

### Requirement: Humanized status labels
The timeseries feature SHALL display a feature's `status` to the user through a humanizing lookup
rather than the raw upstream value. The per-source display config MAY declare a
`statusLabels` table mapping a raw status code to a human-readable label; the lookup SHALL resolve a raw code against every source's `statusLabels` table (raw codes with
labels SHALL therefore be unique across sources), and a code found in no table SHALL fall back to
the existing `catLabel()` humanizer. This lookup SHALL be the single place status labels are
produced and SHALL be applied at every surface
that shows a status to the user: the map marker popup, the map timeline-point tooltip, the incident
table's status cell, the detail panel's observation history, the EPB detail row, and the status
filter dropdown's option text.

The `epb` source SHALL populate `statusLabels` with `OUTAGE_REPORTED`→"Outage",
`EN_ROUTE`→"En Route", `REPAIR_IN_PROGRESS`→"Repairing", `RESTORED`→"Restored", and
`Closed`→"Closed". Sources without machine-code statuses (`hc911`, `tdot`, `tnaw`) SHALL
declare no `statusLabels` and keep their `catLabel()`-humanized display unchanged.

The humanized label is a display concern only: `properties.status` SHALL continue to carry the raw
code, the status filter's stored value and `passesFilters` match SHALL remain the raw code, and the
status filter dropdown's `<option>` value SHALL remain the raw code while only its visible text is
humanized — so selecting a humanized label still filters on the underlying raw status.

#### Scenario: EPB status is humanized wherever it is shown
- **WHEN** an `epb` outage with status `REPAIR_IN_PROGRESS` appears in a popup, the incident table,
  the detail panel history, or the status filter dropdown
- **THEN** each surface displays "Repairing" rather than the raw `REPAIR_IN_PROGRESS`

#### Scenario: Each EPB status code maps to its own label
- **WHEN** an `epb` outage carries status `RESTORED`, and another carries the closure sentinel `Closed`
- **THEN** the first is displayed as "Restored" and the second as "Closed"

#### Scenario: Source without a status table falls back to catLabel
- **WHEN** an `hc911` or `tdot` feature with a status is displayed and its source declares no
  `statusLabels`
- **THEN** its status is shown via the existing `catLabel()` humanizer, unchanged from before

#### Scenario: Filtering still matches the raw code behind a humanized option
- **WHEN** the user selects the "Repairing" option in the status filter dropdown
- **THEN** the stored filter value is the raw `REPAIR_IN_PROGRESS` and only features whose
  `properties.status` equals `REPAIR_IN_PROGRESS` remain visible

## REMOVED Requirements

### Requirement: Behavioral parity with the replaced UI
**Reason**: Migration-era requirement from the vanilla-JS to Svelte port. The feature has since gained glyph markers, polygons, viewport persistence, humanized statuses, and themed basemaps, so "no new user-facing behavior" no longer holds.
**Migration**: None. The current behavior is specified by the feature's other requirements.
