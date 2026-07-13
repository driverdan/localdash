# Design: add-theme-switcher

## Context

`establish-styling-contract` makes the whole UI restyleable from global stylesheets that target
semantic markup hooks. This change adds the user-facing theme system on top. Two constraints shape
it: the app is a single Vite-built SPA served by FastAPI (no per-route stylesheet negotiation), and
we just shipped `frontend-preferences` (localStorage, runes-store-applied) — theme is another
preference but with a stricter timing requirement the prefs system does not have.

## Goals / Non-Goals

**Goals:**

- Users switch the whole site between named themes from a control in the shell.
- Themes can change layout, typography, and color — not just color.
- The choice persists and is applied before first paint (no flash of the wrong theme).
- The map basemap matches the active theme.
- At least one alternate (dark) theme ships as proof.

**Non-Goals:**

- No `prefers-color-scheme`/OS-following "system" theme in this change (a possible later addition;
  the registry leaves room for it). Themes are a manual user pick here.
- No per-user server-side theme storage; per-browser localStorage only.
- No theme *authoring* UI; themes are code in the registry.
- No change to the styling contract itself (that is the prior change).

## Decisions

### 1. Apply via `data-theme` on the root, not by swapping stylesheets

Set `document.documentElement.dataset.theme = name`; author each theme as CSS scoped under
`[data-theme="<name>"] …`. All themes ship in the bundle and switching is a single attribute write —
instant, no network, no flash. The alternative (swapping `<link href>` per theme) enables lazy
loading but fights Vite's bundling and makes instant switching harder; for a handful of themes the
attribute model is simpler and strictly better UX. Cost accepted: every theme's rules are always in
the bundle (small at this scale).

### 2. A theme registry in `lib/`

One module (e.g. `frontend/src/lib/theme.svelte.ts`) owns: the list of theme `{ id, label }`, the
current selection (reactive, for the switcher), `applyTheme(id)` (writes `data-theme` + persists),
and each theme's **basemap override** (see decision 4). The registry is the single place a new theme
is registered — add an entry + a `[data-theme="…"]` stylesheet, nothing else. This mirrors the
"add a source = one config entry" and "add a feature = one route" conventions the codebase favors.

### 3. Persistence + pre-paint bootstrap (the FOUC constraint)

Theme differs from every other preference: applying it after the Svelte app mounts means each load
paints the default theme, then snaps to the saved one. The fix is a tiny **synchronous inline
script in `index.html`** that reads the theme key from `localStorage` and sets `data-theme` on
`<html>` before the app bundle loads and before first paint.

```
index.html
  <head>
    <script>                       // inline, synchronous, no bundle dependency
      try {
        var t = localStorage.getItem('localdash.theme');
        if (t) document.documentElement.dataset.theme = t;
      } catch (e) {}
    </script>
  </head>
```

Consequences:

- Theme uses its **own top-level string key** `localdash.theme` (not a JSON blob), so the inline
  script stays trivial and dependency-free. It deliberately does **not** ride the
  `frontend-preferences` runes-store path, which applies post-mount.
- The registry's `applyTheme` writes the same key the inline script reads; the two share that key
  as a contract. The runes store still exposes the reactive current-theme for the switcher UI, but
  the source of truth at load time is the inline script.
- Unknown/absent key → no attribute → CSS falls through to the default theme. Malformed value is
  harmless (it just names a `[data-theme]` block that doesn't exist → default styling).

### 4. Basemap follows the theme, client-side, without touching the backend

The map basemap is a raster tile layer; a dark UI over a bright Carto Voyager basemap is the classic
half-finished dark mode. Rather than extend `/api/v1/config` (which would make a frontend concern
leak into server config), the theme registry carries an optional tile override per theme. `MapView`
selects the basemap as: the active theme's override if present, else the server-provided
`tile_url`. So the default theme keeps the operator-configured basemap, and a dark theme supplies
its own (e.g. Carto `dark_all`) from the registry. When the theme changes while the map is open,
`MapView` swaps the Leaflet tile layer reactively.

- *Why not send both from config*: keeps `app-shell`'s config contract unchanged and keeps
  theme knowledge in one place (the registry). Operators still configure the default basemap.

### 5. Switcher lives in the shell header

The header is the one always-present surface across all routes, and it already owns global shell
concerns (nav, status bar). The switcher reads the registry's theme list and current selection and
calls `applyTheme` on change. Form (dropdown vs toggle vs cycle button) is an implementation detail
for tasks; the requirement is a discoverable control in the shell.

## Risks / Trade-offs

- [Flash of wrong theme on load] → the inline pre-paint script is the explicit mitigation; verify by
  loading with a non-default theme saved and watching the very first paint, not just the settled
  state.
- [Dark shell over light map] → per-theme basemap override in the registry; verify the map visually
  under the alternate theme.
- [Two persistence mechanisms (inline key vs prefs store) drift] → single shared key
  `localdash.theme`, written only by `applyTheme`, read by the inline script; documented as a
  contract in both places.
- [All themes always bundled] → accepted; negligible for a small set. Revisit with lazy `<link>`
  loading only if the theme set grows large.
- [A theme's layout changes expose a markup assumption the contract missed] → surfaces as a real bug
  against `frontend-styling`; fix belongs in the markup (contract), validating the split between the
  two changes.

## Open Questions

- Whether to later add a `system` theme that follows `prefers-color-scheme`. Out of scope here; the
  registry shape (named entries) accommodates it without rework.
