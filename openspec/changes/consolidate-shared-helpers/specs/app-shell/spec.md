## ADDED Requirements

### Requirement: Feature-agnostic shared backend helpers

A backend helper that more than one feature needs SHALL be implemented once, in a module directly
under `app/` that imports only the standard library and never imports from a feature package
(`app.collectors`, `app.events`, `app.news`, `app.weather`, or any later feature package). A helper
that only one feature needs SHALL live inside that feature. Features SHALL NOT import another
feature's internals to reuse a helper. This is the backend counterpart of the `frontend/src/lib/`
import rule.

In particular, the system SHALL have exactly one implementation of each of these:

- normalising a `datetime` to aware UTC
- parsing an ISO-8601 timestamp string to aware UTC, where the time zone assumed for naive values
  is a parameter that defaults to UTC
- building an EWKT point string from a latitude and longitude
- splitting a comma-separated setting into its stripped, non-empty entries

A source-specific rule SHALL stay with the source that needs it, layered on top of the shared
helper rather than built into it. Examples are the hc911 1900-01-01 "no value" sentinel,
CarCruiseFinder's venue-local naive timestamps, and the tribe `Name=BaseURL` entry format.

#### Scenario: Shared modules import no feature

- **WHEN** the imports of the shared backend helper modules under `app/` are inspected
- **THEN** they resolve only to the standard library, and none resolves to a feature package

#### Scenario: Naive timestamps use the caller's zone

- **WHEN** the shared ISO parser receives `2026-01-10T18:00:00` with no time zone argument
- **THEN** it returns `2026-01-10T18:00:00+00:00`
- **AND** when the same value is parsed with `America/New_York` as the naive-value zone, it returns
  `2026-01-10T23:00:00+00:00`

#### Scenario: Unparseable timestamps are missing, not errors

- **WHEN** the shared ISO parser receives an empty string, `None`, a non-string value, or a string
  that is not ISO-8601
- **THEN** it returns no value and raises no exception

#### Scenario: Source timestamps are unchanged by the consolidation

- **WHEN** an existing source fixture (hc911, TDOT, CitySpark, tribe, Meetup, CarCruiseFinder, or
  iCal) is parsed after the consolidation
- **THEN** every event and observation timestamp equals the value parsed before it, so event
  `canonical_key` values do not change

#### Scenario: Malformed tribe calendar entries are still skipped

- **WHEN** `events_tribe_calendars` contains an entry without `=` alongside a valid `Name=BaseURL`
  entry
- **THEN** building the event sources skips the malformed entry with a warning and still builds a
  source for the valid entry
