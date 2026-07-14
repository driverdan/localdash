# frontend-news Specification

## Purpose

The news feed UI served at `/` (the homepage): the frontend counterpart of the `news` spec. A
feature namespace under `frontend/src/features/news/` that renders clustered stories from
`/api/v1/news/stories` with category tabs, feed controls, and a sources footer showing feed health.

## Requirements

### Requirement: News feature namespace
The news UI SHALL live in `frontend/src/features/news/` (mirroring `/api/v1/news/`), following the
established feature layout (typed `api.ts` client, `types.ts`, a runes store, components, and an
`index.ts` public surface) and the shell's import rules: it imports only from itself, `lib/`, and
third-party packages, and the shell consumes it only through `index.ts`. It SHALL be mounted as the
homepage (route `/`).

#### Scenario: News is an isolated feature
- **WHEN** imports under `frontend/src/features/news/` are inspected
- **THEN** none resolve into `frontend/src/features/timeseries/` or any other feature

### Requirement: Story feed rendering
The feed SHALL render one card per story from `GET /api/v1/news/stories`: category badge, a
source badge showing "N sources" (visually distinguished) for multi-outlet stories or the single
outlet's name otherwise, relative time since latest activity, the headline linking to the first
outlet's article (new tab), the summary when present, and one link pill per outlet (outlet name,
that outlet's own headline as hover title, opening in a new tab). Stories SHALL appear newest
activity first. An empty result SHALL show an empty-state message, and a failed load an error
message.

#### Scenario: Multi-source story card
- **WHEN** a story has articles from three outlets
- **THEN** its card shows a "3 sources" badge and three outlet link pills, each opening that
  outlet's article in a new tab

#### Scenario: Failed load is visible
- **WHEN** the stories request fails
- **THEN** the feed area shows an error message instead of stale or blank content

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

### Requirement: Sources footer with feed health
The page SHALL show a sources table from `GET /api/v1/news/sources`: one row per feed with the
outlet name linking to its homepage, section label, article count, relative last-fetch time, and
last fetch status (or "pending" before the first fetch), so a failing feed is visible in the UI.

#### Scenario: Failing feed surfaces in the footer
- **WHEN** a feed's last fetch errored
- **THEN** its row shows the error status while other rows show success

### Requirement: Styles via the global styling contract
The news feature SHALL follow the `frontend-styling` contract: its components SHALL carry no scoped
visual `<style>` blocks, all news styling SHALL live in a global news stylesheet targeting the
feature's semantic hooks, and its markup (feed, category tabs, story cards, sources footer) SHALL
expose semantic classes and state attributes rather than presentational wrappers. This migration
SHALL NOT change the feature's rendered appearance.

#### Scenario: News styling is global and externally overridable
- **WHEN** the news feature's components are inspected
- **THEN** none contains a scoped visual `<style>` block, and the feed, tabs, story cards, and
  sources footer render from a global stylesheet targeting their semantic hooks

#### Scenario: News looks identical after migration
- **WHEN** the news page is viewed before and after the migration
- **THEN** it renders visually identically
