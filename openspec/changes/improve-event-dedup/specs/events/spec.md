# events — delta for improve-event-dedup

## MODIFIED Requirements

### Requirement: Cross-source de-duplication on ingest
Ingest SHALL collapse the same real-world event — whether reported by different sources or
listed more than once by a single source — onto one canonical record, resolving identity in
tiers, strongest signal first:

1. **Source-listing identity**: a raw event SHALL map onto the existing event that already
   carries a link with the same source name and the same source event id (falling back to the
   source URL when the id is absent), provided that event starts on the same UTC day as the
   raw event. A matching listing whose stored event starts on a different UTC day SHALL NOT
   match this tier (recurring feeds may reuse one id across occurrences).
2. **Exact canonical key**: otherwise, a stable hash of the normalized title plus the UTC
   start day-and-hour, as today. Title normalization SHALL lowercase, strip punctuation,
   collapse whitespace, and fold out common stopword tokens (at minimum "a", "an", "and",
   "at", "in", "n", "of", "on", "the", "to", "with"), so variants such as "Cars & Coffee
   Franklin" and "Cars and Coffee Franklin" normalize identically.
3. **Location-gated fuzzy match**: otherwise, the raw event SHALL merge into a stored event
   when all of the following hold:
   - the stored event starts within 2 hours of the raw event;
   - their normalized title token sets match: one is a subset of the other, or they are equal
     — where individual tokens of at least 5 characters compare equal at edit distance ≤ 1
     (tolerating minor typos such as "Oltewah"/"Ooltewah") and shorter tokens must be
     identical — and the smaller token set has at least 2 tokens;
   - their locations agree: both are geocoded and lie within 0.5 miles of each other, or —
     only when at least one side lacks coordinates — their normalized venue names or
     normalized addresses are equal.
   Title similarity alone SHALL NOT merge events: a fuzzy candidate pair with no location
   evidence on either side, or with locations that disagree, SHALL remain separate events.

New identities create an event unless dropped by the ingest radius filter; matches merge:
empty description, venue name, address, and end time are backfilled from the incoming report,
and a still-unlocated event is geocoded from the newly available address. Each distinct
upstream listing SHALL contribute one link per event, unique per
`(event, source_name, source_url)` — so an event merged from two listings of the same source
keeps both URLs — with the link matched by source name and URL on re-ingest (refreshing its
source event id) rather than replaced. A failure in one source SHALL NOT abort ingestion of
the others.

After each ingest cycle, and under the same refresh serialization, a reconciliation pass
SHALL apply the tier-3 matcher pairwise to stored upcoming events within the same UTC day and
merge every matching pair: the earlier-created row survives, the longer title is kept, links
and tags are unioned, missing fields (description, venue name, address, end time, location)
are backfilled from the removed row, and the removed row is deleted. The pass SHALL be
idempotent and its merge count SHALL be reported in the refresh result, so duplicates already
stored before this capability — or pairs that only become mergeable later (e.g. once a
geocode retry resolves coordinates) — heal without manual intervention.

#### Scenario: Same event from two sources merges
- **WHEN** two sources report "Jazz Night!" and "jazz night" with start times in the same UTC hour
- **THEN** one event row exists with two links, one per source

#### Scenario: Within-source duplicate listings merge
- **WHEN** one source lists "Scenic City Street Machines Sonic Cruise In" and "Scenic City
  Street Machines Cruise in" at the same start time with the same venue name, under different
  source URLs
- **THEN** one event row exists carrying both listings' links (same source name, two URLs)

#### Scenario: Stopword and punctuation variants merge exactly
- **WHEN** "Cars & Coffee Franklin" and "Cars and Coffee Franklin" are reported with start
  times in the same UTC hour
- **THEN** they normalize to the same canonical key and one event row exists

#### Scenario: Typo and extra words merge across an hour boundary when locations agree
- **WHEN** "Oltewah Cruise In" and "Ooltewah Cruise In @ Cambridge Square" are reported one
  hour apart with addresses that geocode within half a mile of each other
- **THEN** one event row exists

#### Scenario: Similar franchise titles in different cities stay separate
- **WHEN** "Cars and Coffee Franklin" and "Cars And Coffee Memphis" are reported at the same
  hour with addresses geocoding roughly 200 miles apart
- **THEN** two separate event rows exist

#### Scenario: Fuzzy title match without location evidence stays separate
- **WHEN** two listings with token-subset titles start within 2 hours but neither carries
  coordinates, a venue name, or an address in common
- **THEN** two separate event rows exist

#### Scenario: Recurring listing id does not collapse a series
- **WHEN** a feed reuses one source event id for occurrences of the same event on different
  days
- **THEN** each day's occurrence is a separate event, each linking that id

#### Scenario: Merge backfills missing fields
- **WHEN** an event was stored without an address and a second source reports it with one
- **THEN** the canonical event gains the address and is geocoded from it

#### Scenario: One failing source does not abort the cycle
- **WHEN** one registered source raises during fetch
- **THEN** events from the remaining sources are still ingested

#### Scenario: Repeat ingest is idempotent
- **WHEN** the same source reports the same events on consecutive cycles
- **THEN** no duplicate events or links are created, including for events previously merged
  from multiple listings

#### Scenario: Reconciliation heals stored duplicates
- **WHEN** two stored upcoming events on the same day satisfy the fuzzy matcher (e.g. rows
  created before this capability deployed) and a refresh cycle runs
- **THEN** after the cycle one merged row remains — carrying both rows' links and tags and
  the longer title — and the refresh result counts the merge

#### Scenario: Reconciliation merges pairs that become mergeable later
- **WHEN** two stored same-day events with matching titles were kept separate for lack of
  location evidence and a later geocode resolves their addresses to within half a mile
- **THEN** the next refresh cycle's reconciliation pass merges them

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
- **WHEN** CarCruiseFinder and another source report the same event and the reports match
  under the ingest de-duplication tiers (exact canonical key, or the location-gated fuzzy
  match)
- **THEN** ingest stores one canonical event carrying each source's link

### Requirement: Tags and refresh API
The system SHALL serve `GET /api/v1/events/tags` returning all known tag names sorted, and
`POST /api/v1/events/refresh` which runs a full ingest cycle (serialized with the scheduled job)
and returns the created, merged, skipped-far, and reconciled counts.

#### Scenario: Tags list
- **WHEN** a client requests `GET /api/v1/events/tags` after events tagged `music` and `arts` exist
- **THEN** the response contains `arts` and `music` in sorted order

#### Scenario: Manual refresh reports counts
- **WHEN** a client sends `POST /api/v1/events/refresh`
- **THEN** an ingest cycle runs and the response reports how many events were created and
  merged, how many new far-away events were skipped by the ingest radius filter, and how many
  stored duplicate pairs the reconciliation pass merged
