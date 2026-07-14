## MODIFIED Requirements

### Requirement: Feed controls
The feed SHALL provide: a time-window selector (24 h / 2 d / 3 d / 7 d, default 3 d) that refetches
stories with the corresponding `hours` value; and a "multi-source only" toggle filtering client-side to
stories with more than one outlet. Stories and sources SHALL also auto-reload every 5 minutes without
user action. The manual "Refresh feeds" control SHALL NOT appear in the feed toolbar; it is provided
as a debug-panel action (see `frontend-debug`) — the feed registers a refresh action that POSTs
`/api/v1/news/refresh`, reloads stories and sources on completion, exposes progress/completion status
text, and reports a disabled state while a refresh is in flight. The time-window selection and
multi-source-only toggle SHALL persist in `localdash.news` and restore on load, with the initial story
fetch using the restored `hours` value.

#### Scenario: Window change refetches
- **WHEN** the user changes the window from 3 days to 24 hours
- **THEN** stories are refetched with `hours=24`

#### Scenario: No refresh button in the toolbar
- **WHEN** the feed toolbar is inspected
- **THEN** it contains the window selector and multi-source-only toggle but no "Refresh feeds" button or refresh status text

#### Scenario: Manual refresh runs from the debug panel
- **WHEN** the user opens the debug panel on `/` and clicks the registered "Refresh feeds" action
- **THEN** the action disables, a fetch cycle runs server-side, and on completion the feed and
  sources reload with a status message shown in the debug panel

#### Scenario: Feed controls survive a reload
- **WHEN** the user sets the window to 24 h, enables "multi-source only", and reloads the page
- **THEN** the initial fetch uses `hours=24` and the multi-source-only toggle restores as on
