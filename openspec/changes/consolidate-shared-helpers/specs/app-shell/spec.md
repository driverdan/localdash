## ADDED Requirements

### Requirement: Single implementations of common backend helpers

The backend SHALL have exactly one implementation of each of the following, used by every caller
that needs it:

- normalising a `datetime` to aware UTC
- parsing an ISO-8601 timestamp string to aware UTC, with the time zone assumed for naive values
  as a parameter that defaults to UTC
- building an EWKT point string from a latitude and longitude
- splitting a comma-separated setting into its stripped, non-empty entries
- matching a keyword table against text. The matcher yields the table's keys in table order,
  keeping each key that has any of its keywords as a substring of the space-padded, lower-cased
  text.

A rule that belongs to one particular source SHALL be layered on top of the shared helper rather
than built into it. For example:

- the hc911 1900-01-01 "no value" sentinel
- CarCruiseFinder's venue-local naive timestamps
- the tribe `Name=BaseURL` entry format
- each caller's own keyword vocabulary, and whether it takes the first match or all matches

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

#### Scenario: Keyword matching preserves news categories and event tags

- **WHEN** a news article's title and summary match keywords from more than one category
- **THEN** the classifier's keyword tier still returns the first matching category in its table
  order
- **AND** when an event's title and description match keywords from more than one topic, the tagger
  still returns the set of all matching topics

#### Scenario: Padded keywords match at the edges of the text

- **WHEN** the keyword matcher is given a table containing the keyword `" ai "` and the text
  `AI meetup`
- **THEN** the key for that keyword is matched

#### Scenario: Malformed tribe calendar entries are still skipped

- **WHEN** `events_tribe_calendars` contains an entry without `=` alongside a valid `Name=BaseURL`
  entry
- **THEN** building the event sources skips the malformed entry with a warning and still builds a
  source for the valid entry
