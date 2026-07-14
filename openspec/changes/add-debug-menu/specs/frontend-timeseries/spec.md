## ADDED Requirements

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
