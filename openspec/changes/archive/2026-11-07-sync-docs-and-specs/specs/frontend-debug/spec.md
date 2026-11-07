## MODIFIED Requirements

### Requirement: Debug overlay toggle button
The shell SHALL render a persistent debug toggle button on every route, drawn as the **π** glyph in a
small styled button. The button SHALL be feature-agnostic shell code (`frontend/src/lib/` +
`App.svelte`), consistent with the shell's ownership of the nav, status bar, and theme switcher, and
SHALL NOT depend on any feature. Its styling SHALL be theme-aware (a visible variant in both the
default and dark themes). On desktop-width viewports the button SHALL float fixed in the bottom-right
corner of the screen; on mobile-width viewports (a defined breakpoint) it SHALL instead stay fixed but
centered at the bottom of the screen. Clicking the button SHALL toggle the debug modal open and closed.

#### Scenario: Button present on every route
- **WHEN** the user is on any route (`/`, `/news`, `/map`, or `/events`)
- **THEN** the π debug toggle button is visible

#### Scenario: Desktop position
- **WHEN** the viewport is at desktop width
- **THEN** the π button is fixed in the bottom-right corner of the screen

#### Scenario: Mobile position
- **WHEN** the viewport is below the mobile breakpoint
- **THEN** the π button is fixed at the bottom-center of the screen rather than bottom-right

#### Scenario: Toggle opens and closes the modal
- **WHEN** the user clicks the π button while the debug modal is closed
- **THEN** the modal opens; clicking the button again (or the modal's close control) closes it

### Requirement: Route-aware debug sections
The debug modal SHALL render sections relevant to the current route, alongside shell sections that are present on every route. It SHALL be built as a general
shell that composes always-present sections and route-specific sections, backed by a singleton reactive debug store in
`frontend/src/lib/` (mirroring the timeseries store pattern), so new sections can be added without
changing existing ones. Route-specific content comes from two sources: sections the shell renders for
known routes (e.g. the map section), and feature debug actions registered into the store by the
mounted feature. On routes with neither an applicable route-specific shell section nor any registered feature action
the modal SHALL show a neutral placeholder in place of the route-specific content, indicating that the current view publishes no debug
data. Because the Settings section is always present, the modal SHALL never be entirely empty, and the placeholder SHALL
scope to the route-specific content rather than to the modal as a whole.

#### Scenario: Map route shows the map section
- **WHEN** the debug modal is open on the `/map` route
- **THEN** it renders the map debug section

#### Scenario: Route with a registered action shows it instead of the placeholder
- **WHEN** the debug modal is open on a route whose mounted feature has registered a debug action (e.g. `/news` or `/events`)
- **THEN** it renders that action rather than the "no debug data for this view" placeholder

#### Scenario: Route with no section or action shows a placeholder beside the always-present sections
- **WHEN** the debug modal is open on a route with no route-specific shell section and no registered feature action
- **THEN** it shows a neutral "no debug data for this view" placeholder for the route-specific content, while the
  always-present Settings section still renders
