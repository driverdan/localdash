## MODIFIED Requirements

### Requirement: Detail panel with observation track
Opening an entity's detail SHALL fetch its snapshot (`/entities/{id}`) and its track
(`/entities/{id}/track`) concurrently, render the source-specific detail rows (empty values
omitted), and list the observation history newest-first with timestamp and status. For entities whose
track has point geometry, track points with positions SHALL draw on the map as circle markers joined
by a dashed polyline when the track has more than one point; for non-point (polygon) tracks the on-map
track drawing SHALL be a no-op while the textual history list still renders. If either fetch fails,
the panel SHALL replace its loading indicator with an error message instead of loading
indefinitely, and the failure SHALL NOT surface as an unhandled promise rejection. A failure for an
entity that is no longer the open one SHALL be ignored. Closing the panel SHALL clear any track
drawing from the map.

#### Scenario: Detail shows history and draws the track
- **WHEN** the user opens a point entity that has moved across several observations
- **THEN** the panel lists its observations newest-first and the map shows the track points joined
  by a dashed line

#### Scenario: Polygon entity detail lists history without a point track
- **WHEN** the user opens a `tnaw` advisory entity
- **THEN** the panel lists its status history newest-first and no circle-marker/polyline track is drawn

#### Scenario: Failed detail fetch shows an error
- **WHEN** the user opens an entity and its snapshot or track request fails
- **THEN** the panel shows an error message in place of "Loading…"

#### Scenario: Closing the panel clears the track
- **WHEN** the user closes the detail panel
- **THEN** the track polyline and points are removed from the map
