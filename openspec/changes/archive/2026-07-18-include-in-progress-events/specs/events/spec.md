## MODIFIED Requirements

### Requirement: Events listing API
The system SHALL serve `GET /api/v1/events/items` returning matching events ordered by start time
with count and the distance origin. Each item SHALL include title, description, start/end times,
venue name, address, latitude/longitude (null when unlocated), sorted tag names, all source links,
and `distance_miles` from the origin (null when unlocated). Filters SHALL be: repeatable `topic`
(events carrying any requested tag), `max_miles` with optional `lat`/`lon` origin (defaulting to
the configured center, `center_lat`/`center_lon`; when bounded, unlocated events are excluded),
`upcoming` (default true — only events that have not ended: end time in the future, or, for events
without an end time, start time at or after now), case-insensitive `search` on the title, and a
result `limit` (default 500). Distance filtering SHALL be computed in SQL against the PostGIS
geometry.

#### Scenario: Default listing is upcoming events
- **WHEN** a client requests `GET /api/v1/events/items` with no parameters
- **THEN** only events that have not ended are returned — including events that started in the
  past whose end time is still in the future — ordered by start time, with distances measured
  from the configured center

#### Scenario: In-progress event remains listed until it ends
- **WHEN** an event started an hour ago and its end time is an hour from now
- **THEN** the default listing includes it, and once its end time passes it is excluded

#### Scenario: Started event without an end time is excluded
- **WHEN** an event without an end time started in the past
- **THEN** the default listing excludes it; no end time is assumed or invented

#### Scenario: Distance filter excludes far and unlocated events
- **WHEN** a client requests `?max_miles=15`
- **THEN** events farther than 15 miles from the origin and events without coordinates are
  excluded, and returned items include `distance_miles`

#### Scenario: Topic filter matches any requested tag
- **WHEN** a client requests `?topic=music&topic=food`
- **THEN** exactly the events tagged `music` or `food` (or both) are returned

#### Scenario: Title search
- **WHEN** a client requests `?search=jazz`
- **THEN** only events whose title contains "jazz" case-insensitively are returned

#### Scenario: Overridden center moves the default origin
- **WHEN** the app runs with `center_lat`/`center_lon` overridden via environment and a client
  requests `GET /api/v1/events/items` with no `lat`/`lon`
- **THEN** `distance_miles` and any `max_miles` filtering are measured from the overridden center
