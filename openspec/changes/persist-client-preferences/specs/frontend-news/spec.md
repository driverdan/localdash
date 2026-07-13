# frontend-news Delta

## MODIFIED Requirements

### Requirement: Category tabs with grouped All view
The feed SHALL offer an "All" tab plus one tab per category present in the loaded stories (in the
API's category display order). A category tab SHALL show only that category's stories; the "All"
tab SHALL group stories under category section headings in display order, omitting empty
categories. The active tab SHALL persist in `localdash.news` and restore on load; if the saved tab
is not among the available tabs once stories load, the feed SHALL display the "All" tab instead.

#### Scenario: All view groups by category
- **WHEN** the "All" tab is active and stories span three categories
- **THEN** the feed shows three section headings in display order, each with its stories

#### Scenario: Category tab filters
- **WHEN** the user selects the Sports tab
- **THEN** only sports stories render, ungrouped

#### Scenario: Active tab survives a reload
- **WHEN** the user selects the Sports tab and reloads the page
- **THEN** the Sports tab is active once stories load

#### Scenario: Saved tab with no stories falls back to All
- **WHEN** the saved active tab names a category absent from the loaded stories
- **THEN** the feed displays the "All" view

### Requirement: Feed controls
The feed SHALL provide: a time-window selector (24 h / 2 d / 3 d / 7 d, default 3 d) that refetches
stories with the corresponding `hours` value; a "multi-source only" toggle filtering client-side to
stories with more than one outlet; and a "Refresh feeds" button that POSTs
`/api/v1/news/refresh`, reloads stories and sources when done, shows progress and completion status
text, and is disabled while a refresh is in flight. Stories and sources SHALL also auto-reload
every 5 minutes without user action. The time-window selection and multi-source-only toggle SHALL
persist in `localdash.news` and restore on load, with the initial story fetch using the restored
`hours` value.

#### Scenario: Window change refetches
- **WHEN** the user changes the window from 3 days to 24 hours
- **THEN** stories are refetched with `hours=24`

#### Scenario: Manual refresh round-trip
- **WHEN** the user clicks "Refresh feeds"
- **THEN** the button disables, a fetch cycle runs server-side, and on completion the feed and
  sources reload with a status message

#### Scenario: Feed controls survive a reload
- **WHEN** the user sets the window to 24 h, enables "multi-source only", and reloads the page
- **THEN** the initial fetch uses `hours=24` and the multi-source-only toggle restores as on
