## ADDED Requirements

### Requirement: Chattanooga Zoo scraper source
The system SHALL provide a Chattanooga Zoo source that scrapes the zoo's events listing page
(`https://chattzoo.org/events/zooevents`) and the detail page of each event linked from it,
registered unconditionally as a normal event source in `build_sources()` (no per-source config
flag; the site publishes no machine endpoint — no iCal, feed, REST API, sitemap, JSON-LD,
microdata, or Open Graph tags — so HTML scraping is the only route, and that fragility is
contained by `run_sources()`'s existing per-source failure isolation, matching how
CarCruiseFinder is treated).

Fetching SHALL send the project's standard `user_agent` (the site does not require a browser
User-Agent, so none SHALL be spoofed) and SHALL follow redirects (the listing is served from
the apex domain and links to the `www.` host). The source SHALL request the listing page once
per run and then one detail page per listed event; unlike the CarCruiseFinder source, fetching
detail pages is required here because the listing page carries no dates at all, and it is safe
here because the zoo's detail pages carry no UTC offsets to be wrong.

Extraction SHALL take the title, image, and detail URL from each listing card, and the
occurrence date/time strings and description from the linked detail page. Each raw event
SHALL carry the zoo's venue name, its full postal address, and its fixed coordinates supplied
directly by the source (so the source adds no geocoder load), the detail page URL as its
source link, and no tags (ingest's keyword tagger derives them).

#### Scenario: Registered as a normal source
- **WHEN** the application builds its event sources for a refresh cycle
- **THEN** a Chattanooga Zoo source is registered alongside the other configured event
  sources, with no additional setting required to enable it

#### Scenario: Listing cards are resolved to detail pages
- **WHEN** the listing page is fetched and contains event cards
- **THEN** the title, image URL, and detail URL are taken from each card, and one request is
  made per distinct detail URL

#### Scenario: Coordinates are supplied, not geocoded
- **WHEN** the source produces a raw event
- **THEN** that event carries the zoo's venue name, full postal address, and the zoo's fixed
  latitude and longitude, so ingest performs no geocoding lookup for it

#### Scenario: Missing listing cards yield zero events
- **WHEN** the listing page contains no parseable event cards
- **THEN** the source returns zero raw events and no detail pages are requested

#### Scenario: Broken scrape does not affect other sources
- **WHEN** the listing page request fails during a refresh cycle with other sources registered
- **THEN** the failure is logged, the Chattanooga Zoo source contributes zero events, and
  events from the other sources are still ingested

#### Scenario: One failing detail page does not lose the others
- **WHEN** one linked detail page fails to fetch or cannot be parsed
- **THEN** that event produces no raw events, the failure is logged, and the remaining detail
  pages still produce their events

### Requirement: Year-less zoo date resolution
The zoo's detail pages render occurrences as free text carrying no year (for example
`March 22 | 9:00 AM - 5:00 PM`). The system SHALL resolve each such occurrence to a
timezone-aware UTC start and end time by interpreting the times as venue-local
America/New_York time and selecting, among the candidate dates formed with the previous,
current, and next calendar year, the one falling closest to the current date. An occurrence
whose resolved end time is already past SHALL be discarded.

The system SHALL NOT roll a past-looking occurrence forward into a future year, because the
zoo's pages retain stale occurrences from earlier in the year and doing so would publish
events that do not exist. An occurrence whose date or time cannot be parsed SHALL be skipped
without aborting the remaining occurrences on that page.

#### Scenario: Upcoming date in the current year is kept
- **WHEN** a detail page lists `December 20 | 9:00 AM - 5:00 PM` and the current date is
  2026-07-20
- **THEN** a raw event is produced starting 2026-12-20 at 9:00 AM America/New_York, converted
  to a timezone-aware UTC start time, with a corresponding UTC end time

#### Scenario: Stale past occurrence is dropped, not rolled forward
- **WHEN** a detail page lists `March 22 | 9:00 AM - 5:00 PM` and the current date is
  2026-07-20
- **THEN** the occurrence resolves to 2026-03-22, is recognized as past, and produces no raw
  event — and in particular no 2027 event is produced

#### Scenario: Year rolls over at the December/January boundary
- **WHEN** a detail page lists `January 10 | 10:00 AM - 2:00 PM` and the current date is
  2026-12-20
- **THEN** the occurrence resolves to 2027-01-10, because that candidate is nearer to the
  current date than 2026-01-10, and a raw event is produced

#### Scenario: Unparseable occurrence is skipped
- **WHEN** one occurrence string on a detail page cannot be parsed into a date and time range
- **THEN** that occurrence produces no raw event, the remaining occurrences on the page are
  still processed, and the failure is logged

### Requirement: Zoo multi-date events fan out per occurrence
A single zoo detail page frequently lists several dates for one event (for example Adventure
Days listing four). The system SHALL produce one raw event per surviving occurrence, each
carrying the page's title, description, image, and source URL, and each carrying a
`source_event_id` that combines the page slug with that occurrence's date so the occurrences
remain distinct through ingest's exact source-listing de-duplication tier.

#### Scenario: Multi-date page becomes multiple events
- **WHEN** a detail page lists four dates and three of them are upcoming
- **THEN** three raw events are produced, sharing the page's title, description, image, and
  source URL, and differing in start time and `source_event_id`

#### Scenario: Occurrences are not collapsed by de-duplication
- **WHEN** the multi-occurrence raw events from one detail page are ingested
- **THEN** each occurrence is stored as a distinct event, because their source event ids and
  canonical keys differ by date

#### Scenario: Single-date page becomes one event
- **WHEN** a detail page lists exactly one upcoming date
- **THEN** exactly one raw event is produced for that page

#### Scenario: Fully past page yields nothing
- **WHEN** every date listed on a detail page is already past
- **THEN** that page produces no raw events and the remaining pages are still processed
