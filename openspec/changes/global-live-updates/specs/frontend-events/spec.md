## MODIFIED Requirements

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
