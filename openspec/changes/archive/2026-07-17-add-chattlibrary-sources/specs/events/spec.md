# events — delta for add-chattlibrary-sources

## ADDED Requirements

### Requirement: The Events Calendar (tribe) REST sources
The system SHALL ingest events from WordPress sites running The Events Calendar plugin via its
REST API, `GET <base_url>/wp-json/tribe/events/v1/events`, requesting a date window from today
through a configurable lookahead (`events_tribe_lookahead_days`, default 14 days) and paginating
with `per_page=50` until the response's `total_pages` is exhausted, subject to a defensive page
cap. Calendars SHALL be configured via the `events_tribe_calendars` setting: comma-separated
`Name=BaseURL` entries, defaulting to
`Chattanooga Public Library=https://chattlibrary.org` so a fresh install ingests the library
calendar out of the box, and fully overridable via the environment (including overriding to empty
to disable tribe ingestion). Entries without a `=` separator SHALL be skipped with a logged
warning rather than failing startup. Requests SHALL NOT send authentication or a spoofed browser
User-Agent. Parsing SHALL be a pure function of a page's JSON payload so it is testable offline
with no network.

Each event SHALL map to a raw event as follows: `title` with HTML entities unescaped;
`description` reduced to plain text (HTML markup stripped); `utc_start_date` parsed as an aware
UTC start time (events without it are skipped with a warning); `utc_end_date` as the optional end
time; venue name from `venue.venue` and a geocodable address joined from the venue's street
address, city, state/province, and zip (only non-empty parts); the venue's `geo_lat`/`geo_lng`
supplied as coordinates when present so ingest does not geocode those events; the event image URL
passed through the shared placeholder-image exclusion; the event's category names, lowercased,
supplied as tags so ingest does not keyword-tag those events; the occurrence's `id` (unique per
recurring-series occurrence) as the source event id; the event page `url` as the source link; and
the configured calendar name as the source name.

#### Scenario: Default configuration registers the library calendar
- **WHEN** the application runs without any `EVENTS_TRIBE_CALENDARS` override
- **THEN** the source registry contains one tribe source named "Chattanooga Public Library" for
  `https://chattlibrary.org`

#### Scenario: Override replaces the default
- **WHEN** `EVENTS_TRIBE_CALENDARS` is set to a different comma-separated `Name=BaseURL` list (or
  to empty)
- **THEN** only the configured calendars (or no tribe sources at all) are registered — the
  default calendar is not added back

#### Scenario: Malformed configuration entry is skipped loudly
- **WHEN** `EVENTS_TRIBE_CALENDARS` contains an entry without a `=` separator
- **THEN** that entry is skipped with a logged warning and the remaining calendars are registered

#### Scenario: Date-window pagination fetches all pages
- **WHEN** the API reports `total_pages` greater than one for the requested window
- **THEN** a fetch requests each successive page and returns the events of all pages combined

#### Scenario: Venue geo and categories bypass derivation
- **WHEN** an event's venue carries `geo_lat`/`geo_lng` and the event has category names
- **THEN** the raw event carries those coordinates and the lowercased category names as tags, and
  ingest neither geocodes nor keyword-tags it

#### Scenario: Venue without coordinates falls back to address geocoding
- **WHEN** an event's venue has a postal address but no `geo_lat`/`geo_lng`
- **THEN** the raw event carries the joined address and no coordinates, and ingest geocodes it
  through the existing pipeline

#### Scenario: Event without a UTC start is skipped
- **WHEN** a payload event lacks `utc_start_date`
- **THEN** that event is skipped with a warning and the remaining events are ingested

#### Scenario: HTML is reduced to text
- **WHEN** an event's `description` contains HTML markup and its `title` contains HTML entities
- **THEN** the raw event's description is plain text and its title has entities decoded

#### Scenario: Recurring occurrences remain distinct
- **WHEN** two occurrences of the same recurring series appear in the window
- **THEN** each maps to its own raw event with its own occurrence `id` as source event id and its
  own dated event page URL
