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
User-Agents), SHALL limit itself to the listing page plus a bounded number of event detail
pages per run with a polite delay between requests, and SHALL NOT attempt to access the site's
blocked machine endpoints (iCal export, REST API). Extraction SHALL prefer each detail page's
schema.org `Event` JSON-LD and fall back to HTML selectors when JSON-LD is absent or
unparseable, mapping name → title, start/end dates → timezone-aware UTC times (naive values
interpreted as venue-local time), location name/address → venue name and geocodable address
string (never coordinates), the detail page URL → source link, and a stable per-event
identifier → source event id. Detail pages without a parseable start date SHALL be skipped. A
failure fetching or parsing one detail page SHALL NOT abort the remaining pages, and a failure
of the whole scrape SHALL NOT affect ingestion from other sources.

#### Scenario: Registered as a normal source
- **WHEN** the application builds its event sources for a refresh cycle
- **THEN** a CarCruiseFinder source is registered alongside the other configured event sources,
  with no additional setting required to enable it

#### Scenario: JSON-LD detail page becomes a raw event
- **WHEN** a fetched detail page embeds a schema.org `Event` JSON-LD block with a name, start
  date, and location
- **THEN** one raw event is produced with that title, a timezone-aware UTC start time, the
  venue name and address from the location, the detail page URL as its source link, and no
  coordinates

#### Scenario: Missing JSON-LD falls back to HTML
- **WHEN** a detail page carries no parseable `Event` JSON-LD but its HTML contains the event
  title and date
- **THEN** the raw event is extracted from the HTML fallback selectors

#### Scenario: Undated detail page is skipped
- **WHEN** a detail page yields no parseable start date from JSON-LD or HTML
- **THEN** that page produces no raw event and the remaining detail pages are still processed

#### Scenario: Broken scrape does not affect other sources
- **WHEN** the listing page request fails (e.g. a WAF 403) during a refresh cycle with other
  sources registered
- **THEN** the failure is logged, the CarCruiseFinder source contributes zero events, and
  events from the other sources are still ingested

#### Scenario: Overlap with other car-event sources merges
- **WHEN** CarCruiseFinder and another source report the same event with matching normalized
  titles and start times in the same UTC hour
- **THEN** ingest stores one canonical event carrying one link per source
