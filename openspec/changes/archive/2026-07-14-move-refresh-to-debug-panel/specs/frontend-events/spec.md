## ADDED Requirements

### Requirement: Manual source refresh via the debug panel
The events page SHALL NOT render a "Refresh sources" button or refresh status text in its toolbar.
Manual source refresh is provided as a debug-panel action (see `frontend-debug`): while the `/events`
route is mounted, the feature registers a refresh action that POSTs `/api/v1/events/refresh`, reloads
items and tags on completion, exposes progress/completion status text, and reports a disabled state
while a refresh is in flight; it unregisters the action on teardown. This is separate from and does
not replace the feature's automatic 5-minute reload.

#### Scenario: No refresh button in the toolbar
- **WHEN** the events toolbar is inspected
- **THEN** it contains the search box and topic/distance filters but no "Refresh sources" button or refresh status text

#### Scenario: Manual refresh runs from the debug panel
- **WHEN** the user opens the debug panel on `/events` and clicks the registered "Refresh sources" action
- **THEN** the action disables, a fetch cycle runs server-side, and on completion the items and tags
  reload with a status message shown in the debug panel

#### Scenario: Action is scoped to the route
- **WHEN** the user navigates away from `/events`
- **THEN** the events refresh action is unregistered and no longer appears in the debug panel
