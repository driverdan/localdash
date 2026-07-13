## MODIFIED Requirements

### Requirement: Pluggable event source interface
The events feature SHALL define a pluggable source interface: a `RawEvent` value (title, start
time, source name, source URL, plus optional description, end time, venue name, address, and
source event id — an address only, never coordinates) and an `EventSource` base class whose async
`fetch()` returns the source's current `RawEvent` list. Sources SHALL be registered in a single
build function: configuration-gated sources (iCal feeds via `events_ical_feeds`, Meetup via its
token) remain overridable or removable through configuration alone, and the CarCruiseFinder
scraper is registered unconditionally (no per-source flag; removable only by code change — its
fragility is contained by per-source failure isolation rather than a switch). The shipped
configuration defaults therefore register exactly two sources: the Tennessee car-events iCal
feed and the CarCruiseFinder scraper. No sample/fixture source SHALL be importable by the
application (fixtures live in the test suite only). Adding a source MUST require only a new
source class plus its registration — no changes to ingest, storage, API, or frontend.

#### Scenario: Explicitly emptied configuration leaves only the always-on scraper
- **WHEN** a refresh cycle runs with `events_ical_feeds` set to an empty string and no tokens
  configured
- **THEN** the registry contains only the CarCruiseFinder source and the cycle completes
  successfully

#### Scenario: Sources supply addresses, not coordinates
- **WHEN** a source reports an event
- **THEN** it provides at most a venue name and street address, and coordinates are derived only
  by the ingest pipeline's geocoder

## ADDED Requirements

### Requirement: CarCruiseFinder scraper source
The system SHALL provide a CarCruiseFinder source that scrapes the Chattanooga tag
listing page (`https://carcruisefinder.com/car-shows/tag/chattanooga-tn/`), registered
unconditionally as a normal event source alongside the iCal and Meetup sources in
`build_sources()` (no per-source config flag; the source is fragile — the site's machine
endpoints are WAF-blocked and HTML scraping is the only route — but that fragility is contained
by `run_sources()`'s existing per-source failure isolation, matching how iCal and Meetup are
treated).
Fetching SHALL send a realistic browser User-Agent (the site returns 403 to generic
User-Agents), SHALL request only the single listing page per run, and SHALL NOT attempt to
access the site's blocked machine endpoints (iCal export, REST API) or fetch per-event detail
pages. Extraction SHALL parse the schema.org `Event` nodes embedded in the listing page's
JSON-LD (whether a node appears as a top-level object, in a top-level array, or inside an
`@graph`), mapping name → title, start/end dates → timezone-aware UTC times (naive values
interpreted as venue-local America/New_York time), location name/address → venue name and
geocodable address string (never coordinates, even though the JSON-LD carries them), the
event's own page URL → source link, and a stable per-event identifier derived from that URL →
source event id. Event nodes without a parseable start date SHALL be skipped without aborting
the remaining nodes, a listing page without parseable `Event` JSON-LD SHALL yield zero events,
and a failure of the whole scrape SHALL NOT affect ingestion from other sources.

#### Scenario: Registered as a normal source
- **WHEN** the application builds its event sources for a refresh cycle
- **THEN** a CarCruiseFinder source is registered alongside the other configured event sources,
  with no additional setting required to enable it

#### Scenario: Listing JSON-LD events become raw events
- **WHEN** the fetched listing page embeds schema.org `Event` JSON-LD nodes with names, start
  dates, and locations
- **THEN** one raw event is produced per node with that title, a timezone-aware UTC start time,
  the venue name and joined postal address from the location, the event page URL as its source
  link, and no coordinates

#### Scenario: Only the listing page is requested
- **WHEN** a fetch cycle runs
- **THEN** exactly one HTTP request is made — to the listing page, carrying a realistic browser
  User-Agent — and no per-event detail pages or machine endpoints are requested

#### Scenario: Undated event node is skipped
- **WHEN** one `Event` node in the listing JSON-LD has no parseable start date
- **THEN** that node produces no raw event and the remaining nodes are still processed

#### Scenario: Missing JSON-LD yields zero events
- **WHEN** the listing page contains no parseable `Event` JSON-LD
- **THEN** the source returns zero raw events

#### Scenario: Broken scrape does not affect other sources
- **WHEN** the listing page request fails (e.g. a WAF 403) during a refresh cycle with other
  sources registered
- **THEN** the failure is logged, the CarCruiseFinder source contributes zero events, and
  events from the other sources are still ingested

#### Scenario: Overlap with other car-event sources merges
- **WHEN** CarCruiseFinder and another source report the same event with matching normalized
  titles and start times in the same UTC hour
- **THEN** ingest stores one canonical event carrying one link per source
