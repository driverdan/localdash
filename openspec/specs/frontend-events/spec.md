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
and auto-reload it every 5 minutes (no WebSocket).

#### Scenario: Feature isolation
- **WHEN** imports under `frontend/src/features/events/` are inspected
- **THEN** they resolve only to the feature itself, `frontend/src/lib/`, or third-party packages

#### Scenario: Data loads and refreshes
- **WHEN** the `/events` route mounts
- **THEN** items and tags load from `/api/v1/events/`, and reload automatically after 5 minutes

### Requirement: Event list with source links
The events page SHALL render matching events as a list ordered by start time, each entry showing
the title, start time (and end time when present), venue/address when present, its topic tags,
its distance in miles when located, and one outbound link per reporting source. When no events
match — including the not-yet-any-sources state — the page SHALL show an explicit empty state
rather than a blank region.

#### Scenario: Event card content
- **WHEN** an event with two source links is rendered
- **THEN** its card shows title, time, venue, tags, distance, and two labeled links, one per source

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
