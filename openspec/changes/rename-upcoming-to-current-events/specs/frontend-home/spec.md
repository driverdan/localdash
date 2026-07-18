## RENAMED Requirements

- FROM: `### Requirement: Upcoming events digest widget`
- TO: `### Requirement: Current events digest widget`

## MODIFIED Requirements

### Requirement: Current events digest widget
The events widget SHALL be titled "Current events" and fetch `GET /api/v1/events/items?limit=10`
with no topic, distance, or search parameters — ignoring any event filter preferences persisted
by the events feature — and render up to 10 events, soonest first, as abbreviated digest rows
owned by the home feature (not the events feature's `EventCard`). Each row SHALL show only: the
event title linked to the event's primary source URL (opening in a new tab; plain text when the
event has no links), and the full formatted date/time produced by the shared
`fmtEventDate(starts_at, ends_at)` formatter, followed by the distance in miles when
`distance_miles` is non-null. Rows SHALL NOT show tags, images, venue/address, descriptions, or a
source-link list. A failed load SHALL show an error message inside the widget; an empty result
SHALL show an empty-state message.

#### Scenario: Widget is titled "Current events"
- **WHEN** the home page renders the events digest widget
- **THEN** the widget heading reads "Current events"

#### Scenario: Saved event filters are ignored
- **WHEN** the user has topic and distance filters saved from the events page and opens `/`
- **THEN** the widget's request carries no filter parameters and shows the next 10 events
  regardless of those saved filters

#### Scenario: Next ten events render as abbreviated rows
- **WHEN** the events endpoint returns events
- **THEN** the widget shows at most 10 digest rows ordered by start time ascending, each showing
  only a linked title and a formatted date/time with distance — no tags, image, venue,
  description, or source-link list

#### Scenario: Title links to the primary source
- **WHEN** a digest row renders for an event whose first link has a source URL
- **THEN** the title is a link to that URL that opens in a new tab

#### Scenario: Distance is omitted when unknown
- **WHEN** a digest row renders for an event whose `distance_miles` is null
- **THEN** the row shows the formatted date/time with no distance fragment

#### Scenario: No events
- **WHEN** the events endpoint returns an empty list
- **THEN** the widget shows an empty-state message instead of a blank card
