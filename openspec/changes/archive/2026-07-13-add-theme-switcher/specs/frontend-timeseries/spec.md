# frontend-timeseries Delta

## ADDED Requirements

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
