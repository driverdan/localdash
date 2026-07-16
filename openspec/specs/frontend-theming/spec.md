# frontend-theming Specification

## Purpose

The frontend theme system (`frontend/src/lib/theme.svelte.ts` + per-theme stylesheets), layered on
the `frontend-styling` contract: a named-theme registry, `data-theme` application on the document
root, the switcher control in the shell, pre-paint persistence via a synchronous inline bootstrap in
`index.html`, and per-theme basemap selection. Themes restyle the whole site — layout, typography,
and color — from CSS, and the choice persists per-browser with no server-side storage.

## Requirements

### Requirement: Named theme registry
The frontend SHALL maintain a theme registry (a module under `frontend/src/lib/`) as the single
place a theme is defined: each theme has an id and a human label, the current appearance is the
default theme, and each theme MAY declare a basemap tile override. Registering a new theme SHALL
require only adding a registry entry and a corresponding `[data-theme="<id>"]` stylesheet, with no
changes to feature code. Each theme's styling MAY change layout, typography, and color — not only
color — by targeting the `frontend-styling` semantic hooks and by overriding the `frontend-styling`
design-token layer.

#### Scenario: Adding a theme is a local change
- **WHEN** a developer adds a new theme
- **THEN** it requires one registry entry plus a `[data-theme="<id>"]` stylesheet, and it appears in
  the switcher without edits to any feature component

#### Scenario: A theme changes more than color
- **WHEN** the shipped alternate (dark) theme is active
- **THEN** the site's surfaces, typography, and color all change — demonstrating the theme system
  restyles layout/type, not just colors

### Requirement: Theme application and switching
The active theme SHALL be applied by setting `data-theme` on the document root element, and the app
SHALL provide a discoverable theme switcher in the shell that changes the active theme. Switching
SHALL take effect immediately without a page reload or stylesheet re-fetch. An absent or unknown
`data-theme` value SHALL fall through to the default theme's styling.

#### Scenario: Switching themes is instant
- **WHEN** the user picks a different theme in the switcher
- **THEN** `data-theme` on the root updates and the whole site re-styles immediately, without a
  reload

#### Scenario: Unknown theme falls back to default
- **WHEN** the root carries a `data-theme` value that no registered theme matches
- **THEN** the site renders with the default theme's styling and does not break

### Requirement: Persistence and pre-paint application
The chosen theme SHALL persist in a dedicated top-level `localStorage` key (`localdash.theme`) and
SHALL be applied before first paint by a synchronous inline bootstrap script in `index.html`, so a
reload never flashes the default theme before the saved one. The switcher SHALL write the same key
the bootstrap reads. Theme persistence SHALL NOT depend on the post-mount `frontend-preferences`
store, because it must apply before the app bundle runs. A `localStorage` read failure SHALL be
swallowed, leaving the default theme.

#### Scenario: Saved theme applies with no flash
- **WHEN** a non-default theme is saved and the user reloads the page
- **THEN** the first painted frame is already the saved theme — no flash of the default theme

#### Scenario: Storage unavailable degrades to default
- **WHEN** `localStorage` is unavailable and the page loads
- **THEN** the bootstrap script does not error and the site renders with the default theme

### Requirement: Theme palettes as token overrides
A theme's palette SHALL be expressed by overriding design-token custom properties under its
`[data-theme="<id>"]` selector rather than restating per-element color rules; per-element rules in
a theme sheet are reserved for what tokens cannot express (layout and typography shifts, structural
differences). The shipped dark theme SHALL define its palette this way, using chattanooga.gov's
dark-mode color family.

#### Scenario: Dark palette is a token block
- **WHEN** the dark theme's stylesheet is inspected
- **THEN** its colors are defined as token overrides in a `[data-theme="dark"]` block, and its
  remaining per-element rules change typography or layout rather than restating token-covered
  colors

#### Scenario: Token consumers re-theme automatically
- **WHEN** the dark theme is activated
- **THEN** elements styled via tokens (surfaces, text, links, borders, status colors) take the dark
  values with no dark-theme rule naming those elements individually
