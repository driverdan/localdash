## Why

CARTO's basemaps now require an API key. The tile URLs we use (`rastertiles/voyager` for the default
theme and `dark_all` for the dark theme) still return HTTP 200 PNGs, but every tile now has an
"API KEY REQUIRED" watermark across it. Both themes show a defaced map, and the network panel shows
no error. We want a basemap that needs no key, account, or registration.

## What Changes

- Change the default basemap (`tile_url` / `tile_attribution` in `app/config.py`) from CARTO Voyager
  to the standard OpenStreetMap raster tiles (`https://tile.openstreetmap.org/{z}/{x}/{y}.png`).
  The new attribution string meets the OSM license requirements.
- Change `.env.example` to use the same OSM defaults. It currently points at Esri World_Topo_Map,
  which doesn't match `app/config.py`.
- The dark theme no longer uses its own tile URL. Remove its CARTO `dark_all`
  `tileUrl` / `tileAttribution` override from the theme registry. The dark theme now darkens the same
  OSM tiles with a CSS filter on the Leaflet tile pane only. Markers, polygons, popups, and the
  attribution control are left unfiltered.
- Keep the registry's optional per-theme `tileUrl` override as an extension point. No shipped theme
  uses it after this change.
- Theme switching still restyles the basemap immediately with no reload. The CSS filter applies
  instantly, and the tile layer isn't rebuilt.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `frontend-timeseries`: the "Themed basemap" requirement changes. The dark theme darkens the
  configured basemap through a CSS filter scoped to the tile layer. It no longer depends on swapping
  to a separate dark tile URL. A theme tile-URL override is still honored when a theme declares one.

## Impact

- **Backend**: `app/config.py` defaults only. The `GET /api/v1/config` contract (`tile_url`,
  `tile_attribution`) doesn't change.
- **Frontend**: `frontend/src/lib/theme.svelte.ts` (the dark entry loses its override) and
  `frontend/src/styles/theme-dark.css` (a new tile-pane filter rule). `MapView.svelte` shouldn't
  need changes because its override-or-config logic stays the same.
- **Config/docs**: `.env.example`, and the README if it mentions the provider.
- **External service**: moves from CARTO's CDN to the OSM Foundation tile servers. We must follow the
  [OSM tile usage policy](https://operations.osmfoundation.org/policies/tiles/): visible attribution,
  a Referer sent by the browser (the app sets no restrictive `Referrer-Policy`), and modest traffic.
  That traffic level fits a single-city dashboard.
- **Dependencies**: none added.
