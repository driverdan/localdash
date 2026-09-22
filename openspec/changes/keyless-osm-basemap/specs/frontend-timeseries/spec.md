## MODIFIED Requirements

### Requirement: Themed basemap
The map's basemap SHALL follow the active theme. `MapView` SHALL use the active theme's basemap tile
override when the theme registry declares one. Otherwise it SHALL use the server-configured
`tile_url` from `GET /api/v1/config`, which remains the default theme's basemap. A theme MAY restyle
the configured basemap from its `[data-theme="<id>"]` stylesheet with a CSS filter scoped to the
Leaflet tile pane. Such a filter SHALL NOT apply to markers, polygons, popups, or the attribution
control. The shipped dark theme SHALL declare no tile override. It SHALL darken the configured
basemap with a tile-pane filter, so every theme uses one keyless tile provider. When the theme
changes while the map is open, the basemap SHALL update to match without a page reload, so a dark
theme does not leave a bright basemap under a dark shell. The `app-shell` config contract is
unchanged.

#### Scenario: Default theme uses the configured basemap
- **WHEN** the default theme is active
- **THEN** the map renders with the `tile_url` basemap from `/api/v1/config`

#### Scenario: Dark theme darkens the configured basemap
- **WHEN** the user switches to the dark theme while the map is open
- **THEN** the map keeps the configured `tile_url` tiles, and the dark theme's tile-pane filter
  renders them dark, without a page reload

#### Scenario: Overlays are not filtered
- **WHEN** the dark theme is active
- **THEN** incident markers, polygons, popups, and the attribution control keep their normal colors,
  because only the tile pane is filtered

#### Scenario: A theme tile override is still honored
- **WHEN** a theme in the registry declares a basemap tile override and that theme is active
- **THEN** the map's tile layer uses the override URL and attribution in place of the configured
  `tile_url`
