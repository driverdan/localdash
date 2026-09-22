## Context

The map currently takes its basemap from two places:

- **Default theme**: `tile_url` / `tile_attribution` in `app/config.py`, served to the browser by
  `GET /api/v1/config`. It currently points at CARTO `rastertiles/voyager`.
- **Dark theme**: a `tileUrl` / `tileAttribution` override on the `dark` entry in
  `frontend/src/lib/theme.svelte.ts`. It currently points at CARTO `dark_all`.

`MapView.svelte` uses `theme.tileUrl ?? cfg.tile_url` and rebuilds the Leaflet tile layer when the
theme changes. CARTO now serves a watermarked "API KEY REQUIRED" tile to keyless clients, so both
themes are broken. `.env.example` also disagrees with the default: it sets Esri World_Topo_Map.

We compared these keyless options in explore mode: OSM standard, OSM HOT, Esri legacy canvases,
Stadia (needs a key or a registered domain off localhost), and OpenFreeMap vector (needs MapLibre GL).
The chosen approach is standard OSM tiles for every theme, with a CSS-darkened variant for the dark
theme.

## Goals / Non-Goals

**Goals:**
- A basemap that works for every theme with no API key, account, or domain registration.
- One tile provider, so a single upstream failure can't break only one theme.
- The dark theme still gets a dark basemap, and switching themes stays instant.
- `app/config.py` and `.env.example` agree on the default.

**Non-Goals:**
- Vector tiles or MapLibre.
- Self-hosting or proxying tiles.
- Recreating CARTO's muted cartography. The OSM standard style is busier, and we accept that.
- Changing the `/api/v1/config` contract or `MapView`'s override-or-config logic.

## Decisions

**1. Standard OSM tiles at `https://tile.openstreetmap.org/{z}/{x}/{y}.png`.**
We don't use `{s}` subdomains, which OSM deprecated in favor of a single CDN hostname. We don't use
`{r}` either, because OSM doesn't serve retina tiles. The attribution is
`&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors`, which is
the wording the ODbL/OSMF policy requires.
*Alternatives:* OSM HOT is a softer style but runs on a volunteer server with weaker uptime. Esri's
legacy endpoints are the same kind of legacy endpoint CARTO just locked down. OpenFreeMap looks
closest to CARTO but adds a large new rendering dependency.

**2. The dark theme darkens the tiles in CSS, scoped to `.leaflet-tile-pane`.**
The rule goes in `frontend/src/styles/theme-dark.css`, roughly:
`[data-theme="dark"] .leaflet-tile-pane { filter: invert(1) hue-rotate(180deg) brightness(0.9) contrast(0.9); }`.
Inverting turns the light ground dark. The 180° hue rotation puts water, parks, and roads back near
their original hues, and the brightness/contrast values soften the result. We'll tune the exact
values visually during implementation. Leaflet renders markers (`.leaflet-marker-pane`), vector
polygons (`.leaflet-overlay-pane`), popups (`.leaflet-popup-pane`), and controls in separate
elements, so none of them are filtered. Swapping themes changes only the `data-theme` attribute, so
the filter applies instantly. The tile layer isn't rebuilt and no tiles are re-fetched.
*Alternative:* keep a separate dark tile URL. Every keyless dark raster we found is either
key-gated off localhost (Stadia) or a legacy Esri endpoint.

**3. Keep the registry's optional `tileUrl` / `tileAttribution` fields.**
We only remove the `dark` entry's values. The fields stay available for a future theme that needs a
different provider, and `MapView` doesn't change.

**4. `.env.example` uses the same OSM values as `app/config.py`.**
Someone who copies the example file should get the same map as the built-in default.

## Risks / Trade-offs

- [If an operator sets `TILE_URL` to tiles that are already dark, the dark theme inverts them to
  light] → Document next to the `TILE_URL` setting that the dark theme inverts the configured tiles.
  Operators who need a different dark source can use the registry's `tileUrl` override.
- [The OSM tile usage policy bans heavy use and requires a Referer] → Browsers send the origin as the
  Referer by default, and the app sets no restrictive `Referrer-Policy`. Don't add one. A single-city
  dashboard stays well below the policy's heavy-use threshold. If traffic grows, the answer is a
  caching proxy or a self-hosted tile server, not a policy workaround.
- [Inverted OSM colors look a bit unusual: water ends up dark blue-gray and parks muted] → Accepted.
  We'll tune the filter values during implementation.
- [OSM standard style is busier than Voyager, so colored markers could be harder to pick out] →
  Markers already have a white halo for contrast on both backgrounds. Check this visually after the
  change.

## Migration Plan

This is a config-default and CSS change only. The existing `TILE_URL` / `TILE_ATTRIBUTION` env vars
still override the default. Deploy with a Docker rebuild. To roll back, revert the commit.
Deployments that set `TILE_URL` to CARTO in their own `.env` must update it themselves.
