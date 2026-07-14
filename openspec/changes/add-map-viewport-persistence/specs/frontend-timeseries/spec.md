## ADDED Requirements

### Requirement: Map default view and viewport persistence
The map SHALL open at a default view centered on the Chattanooga, TN area at zoom level **12**
when no viewport has been persisted. The map SHALL persist its viewport — the current zoom level
and center coordinates (latitude and longitude) — to browser storage on Leaflet `moveend` and
`zoomend`, and SHALL restore that persisted viewport on initialization (before the first render of
markers) so a reload resumes where the user left off. Persistence SHALL cover zoom and center only;
the table-driven `flyTo` focus and the detail-track rendering SHALL be unaffected. This SHALL be
in addition to — and not replace — publishing the viewport to the shell debug store.

Restoration SHALL be all-or-nothing: if any persisted field (zoom, latitude, or longitude) is
missing or not a finite number, the map SHALL fall back to the entire default view rather than a
partially restored one.

#### Scenario: Default view on first visit
- **WHEN** the map initializes on the `/map` route with no persisted viewport
- **THEN** it centers on the Chattanooga area at zoom level 12

#### Scenario: Viewport restored after reload
- **WHEN** the user pans and zooms the map, then reloads the page
- **THEN** the map reopens at the same zoom level and center the user last left it at

#### Scenario: Corrupt or partial persisted viewport falls back to default
- **WHEN** the persisted viewport is missing a field or holds a non-finite value and the map initializes
- **THEN** the map opens at the default center and zoom 12, and does not error

#### Scenario: Movement is persisted
- **WHEN** the user pans or zooms the map
- **THEN** the new zoom and center are written to browser storage on `moveend` / `zoomend`
