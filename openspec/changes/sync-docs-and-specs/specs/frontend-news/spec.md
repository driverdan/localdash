## MODIFIED Requirements

### Requirement: Feed controls
The feed SHALL provide: a time-window selector (24 h / 2 d / 3 d / 7 d, default 3 d) that refetches
stories with the corresponding `hours` value; and a "multi-source only" toggle filtering client-side to
stories with more than one outlet. Stories and sources SHALL auto-reload when a `news` update ping
arrives on the shared live-update bus (see `frontend-live`) via a permanent subscription registered
from the app shell (not tied to the `/news` route mount), and on bus reconnect; the feed SHALL NOT
run its own polling interval. The manual "Refresh feeds" control SHALL NOT appear in the feed toolbar;
it is provided as a debug-panel action (see `frontend-debug`) — while `/news` is mounted, the feed registers a refresh action
that POSTs `/api/v1/news/refresh`, reloads stories and sources on completion, exposes
progress/completion status text, and reports a disabled state while a refresh is in flight; it unregisters the action on teardown. The
time-window selection and multi-source-only toggle SHALL persist in `localdash.news` and restore on
load, with the initial story fetch using the restored `hours` value.

#### Scenario: Window change refetches
- **WHEN** the user changes the window from 3 days to 24 hours
- **THEN** stories are refetched with `hours=24`

#### Scenario: No refresh button in the toolbar
- **WHEN** the feed toolbar is inspected
- **THEN** it contains the window selector and multi-source-only toggle but no "Refresh feeds" button or refresh status text

#### Scenario: Manual refresh runs from the debug panel
- **WHEN** the user opens the debug panel on `/news` and clicks the registered "Refresh feeds" action
- **THEN** the action disables, a fetch cycle runs server-side, and on completion the feed and
  sources reload with a status message shown in the debug panel

#### Scenario: Refresh action is scoped to the route
- **WHEN** the user navigates away from `/news`
- **THEN** the news refresh action is unregistered and no longer appears in the debug panel

#### Scenario: Feed controls survive a reload
- **WHEN** the user sets the window to 24 h, enables "multi-source only", and reloads the page
- **THEN** the initial fetch uses `hours=24` and the multi-source-only toggle restores as on

#### Scenario: Update ping reloads the feed
- **WHEN** a `{topic: "news", type: "updated"}` message arrives on the shared bus
- **THEN** stories and sources refetch with the current `hours` value, on whatever route the user
  is viewing

### Requirement: Sources footer with feed health
The page SHALL show a sources table from `GET /api/v1/news/sources`: one row per feed with the
outlet name linking to its homepage, the feed's registered section label, the outlet's article
count, relative last-fetch time, and last fetch status (or "pending" before the first fetch), so a
failing feed is visible in the UI. Because article categories are derived from content rather than
from the feed, the API reports article counts per outlet; every feed row of an outlet therefore
shows that outlet's total.

#### Scenario: Failing feed surfaces in the footer
- **WHEN** a feed's last fetch errored
- **THEN** its row shows the error status while other rows show success
