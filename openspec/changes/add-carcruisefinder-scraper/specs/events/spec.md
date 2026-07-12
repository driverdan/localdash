## ADDED Requirements

### Requirement: CarCruiseFinder scraper source (experimental)
The system SHALL provide an experimental CarCruiseFinder source that scrapes the Chattanooga tag
listing page (`https://carcruisefinder.com/car-shows/tag/chattanooga-tn/`), registered only when
the `events_carcruisefinder_enabled` setting is true (default **false**, because the source is
fragile: the site's machine endpoints are WAF-blocked and HTML scraping is the only route).
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

#### Scenario: Flag gates registration
- **WHEN** the application starts with `events_carcruisefinder_enabled` unset (default false)
- **THEN** no CarCruiseFinder source is registered and no requests to carcruisefinder.com occur

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
