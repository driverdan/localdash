## RENAMED Requirements

- FROM: `### Requirement: Current events digest widget`
- TO: `### Requirement: Today's events digest widget`

## MODIFIED Requirements

### Requirement: Today's events digest widget
The events widget SHALL be titled "Today's events" and fetch `GET /api/v1/events/items?limit=10&max_miles=35`
— always applying a fixed 35-mile distance cap from the configured center while ignoring any
topic, search, or persisted distance preferences from the events feature. From the fetched results
(soonest first) the widget SHALL render only events that start on the viewer's current local
calendar day — using the same local-day boundary the shared `fmtEventDate(starts_at, ends_at)`
formatter uses to label a start as "Today" — dropping any event that starts on a later day; the
`limit` of 10 therefore acts as a display cap on the same-day list. Each row SHALL be an
abbreviated digest row owned by the home feature (not the events feature's `EventCard`) showing
only: the event title linked to the event's primary source URL (opening in a new tab; plain text
when the event has no links), and the full formatted date/time produced by `fmtEventDate`,
followed by the distance in miles when `distance_miles` is non-null. Rows SHALL NOT show tags,
images, venue/address, descriptions, or a source-link list. A failed load SHALL show an error
message inside the widget; when no fetched event starts on the current local day the widget SHALL
show an empty-state message.

#### Scenario: Widget is titled "Today's events"
- **WHEN** the home page renders the events digest widget
- **THEN** the widget heading reads "Today's events"

#### Scenario: Request is capped at 35 miles
- **WHEN** the home page loads the events digest
- **THEN** the request carries `max_miles=35` and only events within 35 miles of the configured
  center appear

#### Scenario: Saved event filters are ignored
- **WHEN** the user has topic and distance filters saved from the events page and opens `/`
- **THEN** the widget's request carries no topic or search parameters and a fixed `max_miles=35`
  distance cap regardless of the saved distance preference

#### Scenario: Only events starting today render
- **WHEN** the events endpoint returns events that start on several different days
- **THEN** the widget shows at most 10 digest rows, ordered by start time ascending, and includes
  only events whose start falls on the viewer's current local calendar day

#### Scenario: Events starting on a later day are excluded
- **WHEN** every event the endpoint returns starts on a later calendar day than today
- **THEN** the widget shows the empty-state message rather than any of those later events

#### Scenario: Row shape is abbreviated
- **WHEN** a digest row renders for a same-day event
- **THEN** it shows only a linked title and a formatted date/time with distance — no tags, image,
  venue, description, or source-link list

#### Scenario: Title links to the primary source
- **WHEN** a digest row renders for an event whose first link has a source URL
- **THEN** the title is a link to that URL that opens in a new tab

#### Scenario: Distance is omitted when unknown
- **WHEN** a digest row renders for an event whose `distance_miles` is null
- **THEN** the row shows the formatted date/time with no distance fragment

#### Scenario: No events today
- **WHEN** no event returned by the endpoint starts on the current local day
- **THEN** the widget shows an empty-state message instead of a blank card
