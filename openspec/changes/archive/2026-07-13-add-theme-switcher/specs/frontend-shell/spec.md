# frontend-shell Delta

## ADDED Requirements

### Requirement: Shell hosts theming
The application shell SHALL host the theme system's user-facing and bootstrap surfaces: a
discoverable theme switcher rendered in the header (the always-present surface across all routes),
and a synchronous inline bootstrap script in `index.html` that applies the saved theme to the
document root before the app bundle loads. The switcher SHALL be feature-agnostic shell code
(`frontend/src/lib/` + `App.svelte`/header), consistent with the shell's ownership of nav and the
status bar.

#### Scenario: Switcher is present on every route
- **WHEN** the user is on any route (map, news, or events)
- **THEN** the header shows the theme switcher, and changing it re-styles the current page
  immediately

#### Scenario: Bootstrap runs before the app bundle
- **WHEN** `index.html` loads
- **THEN** the inline theme bootstrap script runs and sets the document-root theme before the app
  bundle initializes, so the shell and first route paint in the saved theme
