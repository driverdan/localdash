## ADDED Requirements

### Requirement: Debug overlay toggle button
The shell SHALL render a persistent debug toggle button on every route, drawn as the **π** glyph in a
small styled button. The button SHALL be feature-agnostic shell code (`frontend/src/lib/` +
`App.svelte`), consistent with the shell's ownership of the nav, status bar, and theme switcher, and
SHALL NOT depend on any feature. Its styling SHALL be theme-aware (a visible variant in both the
default and dark themes). On desktop-width viewports the button SHALL float fixed in the bottom-right
corner of the screen; on mobile-width viewports (a defined breakpoint) it SHALL instead sit at the
bottom of the page. Clicking the button SHALL toggle the debug modal open and closed.

#### Scenario: Button present on every route
- **WHEN** the user is on any route (`/`, `/map`, or `/events`)
- **THEN** the π debug toggle button is visible

#### Scenario: Desktop position
- **WHEN** the viewport is at desktop width
- **THEN** the π button is fixed in the bottom-right corner of the screen

#### Scenario: Mobile position
- **WHEN** the viewport is below the mobile breakpoint
- **THEN** the π button is positioned at the bottom of the page rather than floating bottom-right

#### Scenario: Toggle opens and closes the modal
- **WHEN** the user clicks the π button while the debug modal is closed
- **THEN** the modal opens; clicking the button again (or the modal's close control) closes it

### Requirement: Debug modal placement
The debug modal SHALL be anchored to the top-right of the main body when open, offset from the
timeseries incident detail panel so that both can be open at the same time without overlapping. The
modal SHALL be theme-aware and SHALL provide a close control.

#### Scenario: Modal opens top-right of the main body
- **WHEN** the debug modal is opened
- **THEN** it appears anchored to the top-right of the main body

#### Scenario: Coexists with the incident detail panel
- **WHEN** an incident detail panel is open on the `/map` route and the user opens the debug modal
- **THEN** both panels are visible at once and neither overlaps the other

### Requirement: Route-aware debug sections
The debug modal SHALL render sections relevant to the current route. It SHALL be built as a general
shell that composes route-specific sections, backed by a singleton reactive debug store in
`frontend/src/lib/` (mirroring the timeseries store pattern), so new sections can be added without
changing existing ones. On routes with no applicable section the modal SHALL show a neutral
placeholder rather than being empty or erroring.

#### Scenario: Map route shows the map section
- **WHEN** the debug modal is open on the `/map` route
- **THEN** it renders the map debug section

#### Scenario: Non-map route shows a placeholder
- **WHEN** the debug modal is open on a route with no debug section (e.g. `/` or `/events`)
- **THEN** it shows a neutral "no debug data for this view" placeholder instead of an empty or broken
  panel

### Requirement: Map debug section
On the `/map` route the debug modal SHALL display the map's current **zoom level** and the
**latitude and longitude of the map center**, read from the shell debug store. These values SHALL
update live as the user pans and zooms the map.

#### Scenario: Shows current zoom and center
- **WHEN** the debug modal is open on `/map`
- **THEN** it displays the map's current zoom level and the lat/lng of the map center

#### Scenario: Updates as the map moves
- **WHEN** the user pans or zooms the map while the debug modal is open
- **THEN** the displayed zoom level and center coordinates update to match the new viewport
