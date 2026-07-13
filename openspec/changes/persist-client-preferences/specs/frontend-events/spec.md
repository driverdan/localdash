# frontend-events Delta

## MODIFIED Requirements

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
