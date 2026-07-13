# events Specification (delta)

## ADDED Requirements

### Requirement: Local fixtures source
The system SHALL provide a local fixtures event source: a code-as-config registry (analogous to
the news outlet registry) of well-known recurring local events that publish no machine-readable
feed. Each fixture entry SHALL declare a slug, title, description, venue name, geocodable address,
an organizer `source_url`, local wall-clock start/end times in the America/New_York zone, and
exactly one recurrence form: a recurrence rule (for repeating events) or explicit dates (for
annual events whose editions are only known once announced — dates are never extrapolated to
future years). On each fetch the source SHALL expand fixtures into concrete `RawEvent`s only
within a bounded upcoming horizon of now to now plus 90 days, converting each occurrence's local
times to timezone-aware UTC (correct across DST transitions), emitting one event per day for
multi-day explicit-date fixtures, and assigning each occurrence a deterministic source event id of
`<fixture-slug>-<local-date>` so repeated ingests are idempotent. Expansion SHALL be a pure
function of the fixture and an explicit time window. The source SHALL be registered only when the
`events_fixtures_enabled` setting (default true) is enabled, and SHALL perform no network I/O —
coordinates come only from the ingest pipeline's geocoder.

#### Scenario: Recurrence rule expands within the horizon
- **WHEN** a fixture recurs on the 3rd Sunday of each month from March through November and the
  expansion window covers July 1 to September 29
- **THEN** exactly the July, August, and September 3rd-Sunday occurrences are emitted, each with
  the fixture's title, venue name, address, organizer source URL, and UTC start/end times

#### Scenario: Out-of-season window emits nothing
- **WHEN** a fixture recurs only March through November and the expansion window covers
  December through February
- **THEN** the fixture emits no events

#### Scenario: Local times convert correctly across DST
- **WHEN** a fixture declares an 8:00 AM local start and the window contains occurrences on both
  sides of a daylight-saving transition
- **THEN** each emitted start time is the aware-UTC instant of 8:00 AM America/New_York on that
  date (12:00Z under EDT, 13:00Z under EST)

#### Scenario: Multi-day explicit-date fixture emits one event per day
- **WHEN** an annual fixture lists explicit dates January 9–11 and the window contains them
- **THEN** three events are emitted, one per day, each carrying that day's start and end times

#### Scenario: Repeat ingest is idempotent
- **WHEN** the fixtures source is fetched and ingested on two consecutive cycles
- **THEN** each occurrence carries the same deterministic source event id both times and no
  duplicate events or links are created

#### Scenario: Setting gates registration
- **WHEN** the application starts with `events_fixtures_enabled=false`
- **THEN** the fixtures source is not registered and no fixture events are ingested

#### Scenario: Stale fixture logs a review warning
- **WHEN** a fixture yields no occurrences within the horizon and none within the next 366 days
- **THEN** the fetch logs a warning naming that fixture as needing review, and the cycle
  continues normally

### Requirement: Seed fixture registry
The fixtures registry SHALL be seeded with three verified Chattanooga car events (the mechanism
itself is generic, not car-specific): Chattanooga Cars and Coffee (3rd Sunday monthly, March
through November, 8:00 AM–12:00 PM local, Chattanooga State Community College, linking
https://chattanoogacarsandcoffee.com/), Riverside Chattanooga (annual multi-day event in March at
Finley Stadium / First Horizon Pavilion, explicit dates per announced edition, linking
https://www.riversidechattanooga.com/), and World of Wheels Chattanooga (annual indoor show in
January at the Chattanooga Convention Center, explicit dates per announced edition — the 2026
edition was January 9–11, linking https://worldofwheels.net/chattanooga/). Every seeded entry's
`source_url` SHALL point at the organizer's page so users can verify against drift, and
explicit-date entries SHALL be reviewed and re-dated when their editions pass.

#### Scenario: Registry entries are well-formed
- **WHEN** the seeded registry is validated
- **THEN** every fixture has a unique slug, a non-empty title, address, and organizer source URL,
  and exactly one of a recurrence rule or explicit dates

#### Scenario: Flagship monthly meet is emitted in season
- **WHEN** a fetch runs with a horizon that includes a March-through-November 3rd Sunday
- **THEN** a Chattanooga Cars and Coffee event at Chattanooga State Community College is emitted
  linking the organizer's site

## MODIFIED Requirements

### Requirement: Pluggable event source interface
The events feature SHALL define a pluggable source interface: a `RawEvent` value (title, start
time, source name, source URL, plus optional description, end time, venue name, address, and
source event id — an address only, never coordinates) and an `EventSource` base class whose async
`fetch()` returns the source's current `RawEvent` list. Sources SHALL be registered in a single
build function: configuration-gated sources (iCal feeds via `events_ical_feeds`, Meetup via its
token, the local fixtures registry via `events_fixtures_enabled`) remain overridable or removable
through configuration alone, and the CarCruiseFinder scraper is registered unconditionally (no
per-source flag; removable only by code change — its fragility is contained by per-source failure
isolation rather than a switch). The shipped configuration defaults therefore register exactly
three sources: the Tennessee car-events iCal feed, the CarCruiseFinder scraper, and the local
fixtures source. No sample/demo-data source SHALL be importable by the application (test doubles
live in the test suite only; curated code-as-config registries of real events, such as the local
fixtures source, are permitted). Adding a source MUST require only a new source class plus its
registration — no changes to ingest, storage, API, or frontend.

#### Scenario: Explicitly emptied configuration leaves only the always-on scraper
- **WHEN** a refresh cycle runs with `events_ical_feeds` set to an empty string, no tokens
  configured, and `events_fixtures_enabled` disabled
- **THEN** the registry contains only the CarCruiseFinder source and the cycle completes
  successfully

#### Scenario: Sources supply addresses, not coordinates
- **WHEN** a source reports an event
- **THEN** it provides at most a venue name and street address, and coordinates are derived only
  by the ingest pipeline's geocoder
