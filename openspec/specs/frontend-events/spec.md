# frontend-events Specification

## Purpose

The `/events` page: an event list UI with topic/distance/search filtering and per-source
origin links, following the feature-namespace and runes-store conventions beside `frontend-news`
and `frontend-timeseries`.

## Requirements

### Requirement: Events page feature module
The events UI SHALL live in `frontend/src/features/events/` following the feature-namespace
conventions: a Svelte 5 runes store holding items, tags, active filters, and load status; an API
module calling only `/api/v1/events/` endpoints; and an `index.ts` public surface consumed by
`App.svelte`. The feature SHALL NOT import from other features, and SHALL load its data on mount
and auto-reload it when an `events` update ping arrives on the shared live-update bus (see
`frontend-live`) via a permanent subscription registered from the app shell (not tied to the
`/events` route mount), and on bus reconnect — reloads preserve the active topic/distance/search
filters, and the feature SHALL NOT run its own polling interval.

#### Scenario: Feature isolation
- **WHEN** imports under `frontend/src/features/events/` are inspected
- **THEN** they resolve only to the feature itself, `frontend/src/lib/`, or third-party packages

#### Scenario: Data loads and refreshes
- **WHEN** the `/events` route mounts
- **THEN** items and tags load from `/api/v1/events/`, and reload automatically when an
  `{topic: "events", type: "updated"}` message arrives on the shared bus, with the active filters
  applied to the refetch

### Requirement: Event list with source links
The events page SHALL render matching events as a list ordered by start time, each entry showing
the title, start date and time (and end time when present), venue/address when present, its topic
tags, its distance in miles when located, and one outbound link per reporting source. When the
event has an `image_url`, the card SHALL render it as a lazily loaded lead image (decorative —
empty alt text), following the news story card's conditional-image pattern; an event without an
image SHALL render exactly as before, with no reserved empty image region. When no events match —
including the not-yet-any-sources state — the page SHALL show an explicit empty state rather than
a blank region.

The start date SHALL render as natural language relative to the viewer's local calendar day:
`Today` for the same day, `Tomorrow` for the next day, the weekday name (e.g. `Saturday`) for
events 2–6 days out, and a formatted date (e.g. `Sat, Jul 25`) for events 7 or more days out,
including the year only when it differs from the current year. Times SHALL render without
seconds, with the end time appended when present, e.g. `Today · 7:00 PM – 9:00 PM`.

#### Scenario: Event card content
- **WHEN** an event with two source links is rendered
- **THEN** its card shows title, date and time, venue, tags, distance, and two labeled links, one per source

#### Scenario: Event starting the same local day
- **WHEN** an event starting later on the current local calendar day is rendered
- **THEN** its date shows as `Today` followed by the seconds-free start time

#### Scenario: Event starting the next local day
- **WHEN** an event starting on the next local calendar day is rendered
- **THEN** its date shows as `Tomorrow` followed by the seconds-free start time

#### Scenario: Event within the week
- **WHEN** an event starting 2–6 local calendar days from now is rendered
- **THEN** its date shows as the weekday name (e.g. `Saturday`) followed by the start time

#### Scenario: Event a week or more away
- **WHEN** an event starting 7 or more local calendar days from now is rendered
- **THEN** its date shows as a formatted date (e.g. `Sat, Jul 25`), with the year included only
  when it differs from the current year

#### Scenario: Event with an end time
- **WHEN** an event whose `ends_at` is set is rendered
- **THEN** the end time is appended after an en dash, e.g. `Today · 7:00 PM – 9:00 PM`, with no
  seconds shown

#### Scenario: Event card with an image
- **WHEN** an event whose `image_url` is set is rendered
- **THEN** its card shows the image, loaded lazily, alongside the existing text content

#### Scenario: Event card without an image
- **WHEN** an event whose `image_url` is null is rendered
- **THEN** its card shows no image element and no empty placeholder region

#### Scenario: Empty state
- **WHEN** the API returns zero items
- **THEN** the page shows an empty-state message instead of an empty list

### Requirement: Topic, distance, and search filtering
The events page SHALL offer topic chips (from `GET /api/v1/events/tags`, multi-select), a maximum
distance control, and a title search box. Changing any filter SHALL refetch
`GET /api/v1/events/items` with the corresponding query parameters (server-side filtering), and
active filters SHALL be visually indicated. Selected topics and the maximum distance SHALL persist
in `localdash.events` and restore on load (saved topics intersected with the currently available
tags); the search box SHALL NOT persist and starts empty on every load.

#### Scenario: Topic chips filter server-side
- **WHEN** the user selects the `music` and `food` chips
- **THEN** the list refetches with `topic=music&topic=food` and shows only matching events

#### Scenario: Distance filter
- **WHEN** the user sets a 15-mile maximum
- **THEN** the list refetches with `max_miles=15` and unlocated events disappear from the list

#### Scenario: Search filter
- **WHEN** the user types "jazz" in the search box
- **THEN** the list refetches with `search=jazz` and shows only title matches

#### Scenario: Topic and distance selections survive a reload
- **WHEN** the user selects the `music` chip, sets a 15-mile maximum, and reloads the page
- **THEN** the `music` chip is selected, the distance control shows 15 miles, and the initial fetch
  carries `topic=music&max_miles=15`

### Requirement: Styles via the global styling contract
The events feature SHALL follow the `frontend-styling` contract: its components SHALL carry no
scoped visual `<style>` blocks, all events styling SHALL live in a global events stylesheet
targeting the feature's semantic hooks, and its markup (page toolbar, topic chips, event cards)
SHALL expose semantic classes and state attributes rather than presentational wrappers. This
migration SHALL NOT change the feature's rendered appearance.

#### Scenario: Events styling is global and externally overridable
- **WHEN** the events feature's components are inspected
- **THEN** none contains a scoped visual `<style>` block, and the toolbar, chips, and event cards
  render from a global stylesheet targeting their semantic hooks

#### Scenario: Events looks identical after migration
- **WHEN** the events page is viewed before and after the migration
- **THEN** it renders visually identically

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
