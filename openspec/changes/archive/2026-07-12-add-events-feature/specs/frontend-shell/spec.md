## MODIFIED Requirements

### Requirement: Client-side path routing
The shell SHALL provide a minimal path router in `frontend/src/lib/` (no external routing
dependency): it tracks the current path as reactive state, navigates via the History API
(`pushState` plus a `popstate` listener, so back/forward work), and lets `App.svelte` map paths to
features. The route table SHALL be: `/` renders the news feature, `/map` renders the
timeseries feature, and `/events` renders the events feature. The shell SHALL render a persistent
navigation header linking the routes. Feature-specific UI (such as the timeseries connection
indicator) SHALL appear only on that feature's route.

#### Scenario: Nav switches features without a reload
- **WHEN** the user clicks "Map" in the nav from the news homepage
- **THEN** the URL becomes `/map` and the timeseries dashboard renders without a full page load

#### Scenario: Events route renders the events feature
- **WHEN** the user clicks "Events" in the nav
- **THEN** the URL becomes `/events` and the events feature renders without a full page load

#### Scenario: Browser history works
- **WHEN** the user navigates `/` → `/map` and presses the browser back button
- **THEN** the news feature renders at `/` without a full page load

#### Scenario: Timeseries indicator is scoped to its route
- **WHEN** the news route is active
- **THEN** the timeseries WebSocket connection indicator is not shown
