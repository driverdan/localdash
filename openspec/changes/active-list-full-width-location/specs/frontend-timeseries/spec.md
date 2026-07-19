## MODIFIED Requirements

### Requirement: Incident table
The sidebar SHALL show all currently visible entities sorted by `last_seen_at` descending, with a
live count. Each entity SHALL render its source, category (with color dot), status, and type in a
header row, and its location as a full-width sub-line grouped beneath that header row so long
location text wraps across the whole sidebar width. When an entity's location text is empty (e.g.
`epb` outages), the location sub-line SHALL be omitted and the entity SHALL render as a single row.
The table header SHALL show source, category, status, and type (no location column). Each entity —
its header row together with any location sub-line — SHALL be a single clickable unit: clicking it
SHALL open the entity's detail panel and focus the map on the entity, flying to its coordinates for
point entities, or fitting the map to the affected-area bounds for polygon entities.

#### Scenario: Location renders as a full-width sub-line
- **WHEN** an active `tnaw` water advisory with a long location message is visible
- **THEN** its source, category, status, and type appear in a header row and the location message
  wraps across the full sidebar width on a sub-line grouped beneath that header row

#### Scenario: Empty location collapses to a single row
- **WHEN** an active `epb` outage (whose location text is empty) is visible
- **THEN** the entity renders as a single header row with no empty location sub-line

#### Scenario: Row click focuses a point entity
- **WHEN** the user clicks a table row for a point entity with a position
- **THEN** the detail panel opens for that entity and the map flies to its coordinates

#### Scenario: Row click focuses a polygon entity
- **WHEN** the user clicks a table row for a polygon entity (e.g. a `tnaw` advisory)
- **THEN** the detail panel opens and the map fits the advisory's affected-area bounds

#### Scenario: Clicking the location sub-line focuses the entity
- **WHEN** the user clicks an entity's full-width location sub-line
- **THEN** the same entity's detail panel opens and the map focuses on it, identically to clicking
  its header row
