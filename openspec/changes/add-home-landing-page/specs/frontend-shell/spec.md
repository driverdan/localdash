## MODIFIED Requirements

### Requirement: Client-side path routing
The shell SHALL provide a minimal path router in `frontend/src/lib/` (no external routing
dependency): it tracks the current path as reactive state, navigates via the History API
(`pushState` plus a `popstate` listener, so back/forward work), and lets `App.svelte` map paths to
features. The route table SHALL be: `/` renders the home feature, `/news` renders the news
feature, `/map` renders the timeseries feature, and `/events` renders the events feature. The
shell SHALL render a persistent navigation header linking the routes. Unknown paths SHALL show a
not-found message linking back to the home page. Feature-specific UI (such as the timeseries
connection indicator) SHALL appear only on that feature's route.

#### Scenario: Root renders the home feature
- **WHEN** the user opens `/`
- **THEN** the home landing page renders, not the news feed

#### Scenario: Nav switches features without a reload
- **WHEN** the user clicks "News" in the nav from the home page
- **THEN** the URL becomes `/news` and the news feed renders without a full page load

#### Scenario: Events route renders the events feature
- **WHEN** the user clicks "Events" in the nav
- **THEN** the URL becomes `/events` and the events feature renders without a full page load

#### Scenario: Browser history works
- **WHEN** the user navigates `/` → `/map` and presses the browser back button
- **THEN** the home feature renders at `/` without a full page load

#### Scenario: Unknown path links home
- **WHEN** the user opens an unrecognized path such as `/nope`
- **THEN** a not-found message renders with a link that navigates to `/`

#### Scenario: Timeseries indicator is scoped to its route
- **WHEN** the home or news route is active
- **THEN** the timeseries WebSocket connection indicator is not shown
