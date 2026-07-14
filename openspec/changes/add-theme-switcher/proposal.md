# Proposal: add-theme-switcher

## Why

Once the `frontend-styling` contract exists (semantic markup hooks + global feature stylesheets,
no scoped visual styles), the site's entire look — layout, typography, and color — becomes
restyleable from CSS. This change adds the user-facing capability that vision was for: a theme
switcher that lets users flip the whole site between named themes, with their choice remembered.

**Depends on `establish-styling-contract`** — themes are layers over the contract's semantic hooks
and cannot work while news/events styling is still scoped inside components.

## What Changes

- Add a **theme registry**: named themes, each a set of global CSS rules scoped under a
  `[data-theme="<name>"]` root selector, free to change layout, fonts, and color — not just color.
  The current appearance becomes the default theme.
- Ship at least one **alternate theme** (a dark theme) that visibly exercises typography and
  surface/layout changes, proving the contract supports more than a color swap.
- Apply the active theme by setting `data-theme` on the document root; switching is instant (no
  stylesheet reload).
- Add a **theme switcher control** in the app shell (header) for easy switching.
- **Persist** the chosen theme in a dedicated `localStorage` key, and apply it **before first
  paint** via a synchronous inline bootstrap script in `index.html`, so no load flashes the wrong
  theme (FOUC).
- Make the **Leaflet basemap follow the active theme**: a dark theme uses a dark tile layer so the
  map doesn't stay bright under a dark shell. The theme registry carries the tile override; the
  server-configured `tile_url` remains the default theme's basemap.

## Capabilities

### New Capabilities

- `frontend-theming`: the theme system — the named-theme registry, `data-theme` application,
  the switcher control, pre-paint persistence/bootstrap, and per-theme basemap selection.

### Modified Capabilities

- `frontend-shell`: adds requirements that the shell hosts the theme switcher and runs the
  pre-paint theme bootstrap in `index.html`.
- `frontend-timeseries`: adds a requirement that the map basemap follows the active theme (the
  theme's tile override when present, else the server-configured `tile_url`). The `app-shell` config
  contract is unchanged — `tile_url` remains the default theme's basemap.

## Impact

- Frontend only; no API or backend change. The map basemap-per-theme is handled client-side in the
  theme registry, so the `/api/v1/config` `tile_url` contract is unchanged (it remains the default
  theme's basemap).
- Affected code: `frontend/index.html` (inline bootstrap script + theme CSS wiring), a new theme
  module in `frontend/src/lib/` (registry + apply/persist), the app shell/header (switcher UI),
  `MapView.svelte` (basemap keyed on active theme), and new per-theme stylesheets layered on the
  `frontend-styling` global sheets.
- Relates to `frontend-preferences` (theme is a persisted preference) but does **not** reuse its
  runes-store mechanism: theme must apply pre-paint, so it uses its own top-level `localStorage`
  key read by the inline bootstrap, not a store applied after mount.
- No new dependencies.
