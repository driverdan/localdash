## MODIFIED Requirements

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

## ADDED Requirements

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
