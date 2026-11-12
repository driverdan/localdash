## MODIFIED Requirements

### Requirement: Client-side path routing
The shell SHALL provide a minimal path router in `frontend/src/lib/` (no external routing
dependency): it tracks the current path as reactive state, navigates via the History API
(`pushState` plus a `popstate` listener, so back/forward work), offers a redirect that replaces
the current history entry (`replaceState`) instead of adding one, and lets `App.svelte` map
paths to features. The route table SHALL be: `/` renders the home feature, `/news` renders the
news feature, `/map` renders the timeseries feature, `/events` renders the events feature,
`/login` renders the auth feature's login page, and `/admin` renders the admin feature's
dashboard page subject to that feature's access rule. On `/login`, a visitor whose signed-in
state is not yet known SHALL see a loading indication, a signed-in admin SHALL be redirected to
`/admin`, and a signed-in non-admin SHALL be redirected to `/`. The shell SHALL render a
persistent navigation header linking the `/`, `/news`, `/map` and `/events` routes; it SHALL
NOT link `/login` or `/admin`. Unknown paths SHALL show a not-found message linking back to the
home page. The header SHALL show the shared live-update bus's connection indicator on every
route, since every feature receives live updates.

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

#### Scenario: Connection indicator shows on every route
- **WHEN** any route (`/`, `/news`, `/map`, `/events`, `/login` or `/admin`) is active
- **THEN** the header shows the live-update bus connection state (live, connecting, or
  disconnected)

#### Scenario: Login route renders the login page
- **WHEN** a visitor without a session opens `/login`
- **THEN** the login page renders

#### Scenario: Signed-in admin leaves the login page
- **WHEN** a signed-in admin opens `/login`, or an admin's login succeeds
- **THEN** the URL becomes `/admin` without a new history entry and the admin dashboard page renders

#### Scenario: Signed-in non-admin leaves the login page
- **WHEN** a signed-in user who is not an admin opens `/login`, or such a user's login succeeds
- **THEN** the URL becomes `/` without a new history entry and the home feature renders

#### Scenario: Redirect does not trap the back button
- **WHEN** the user navigates `/` → `/admin` while signed out, is redirected to `/login`, and presses Back
- **THEN** the home feature renders at `/`

#### Scenario: Auth routes are not in the nav
- **WHEN** the navigation header is rendered on any route
- **THEN** it contains no link to `/login` or `/admin`
