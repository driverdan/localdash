# events Specification

## Purpose

Backend event aggregation, ported from the chattevents PoC: a pluggable, config-driven
source registry (iCal feeds, Meetup), ingest that de-duplicates the same real-world event across
sources, keyword topic tagging, Nominatim geocoding with a permanent cache, PostGIS-backed storage,
a scheduled refresh job, and the `/api/v1/events/` API that the `frontend-events` feature consumes.

## Requirements

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

### Requirement: iCal feed sources
The system SHALL ingest any iCal/ICS feed listed in the `events_ical_feeds` setting
(comma-separated URLs), creating one source per URL. The setting SHALL default to the Tennessee
car-events feed `https://carsandcoffeeevents.com/events/category/tennessee/?ical=1` so a fresh
install ingests real events out of the box, and SHALL remain fully overridable via the
environment (including overriding to empty to disable iCal ingestion). Each fetch SHALL download
the feed over HTTP and parse its `VEVENT` components: summary → title (with an "Untitled event"
fallback), description, `DTSTART` → start time (components without one are skipped; date-only
values become midnight; datetimes are coerced to UTC), `DTEND` → end time, `LOCATION` → both venue
name and geocodable address, `UID` → source event id, and the component `URL` (falling back to the
feed URL) → the source link.

#### Scenario: Default configuration registers the Tennessee car-events feed
- **WHEN** the application runs without any `EVENTS_ICAL_FEEDS` override
- **THEN** the source registry contains one iCal source for
  `https://carsandcoffeeevents.com/events/category/tennessee/?ical=1`

#### Scenario: Override replaces the default
- **WHEN** `EVENTS_ICAL_FEEDS` is set to a different comma-separated URL list (or to empty)
- **THEN** only the configured URLs (or no iCal sources at all) are registered — the default feed
  is not added back

#### Scenario: Configured feed is ingested
- **WHEN** `events_ical_feeds` contains one `.ics` URL whose feed has two dated `VEVENT`s
- **THEN** a refresh cycle ingests two raw events attributed to that feed's source

#### Scenario: Undated components are skipped
- **WHEN** a feed contains a `VEVENT` without a `DTSTART`
- **THEN** that component is skipped and the remaining events are ingested

#### Scenario: Location drives geocoding
- **WHEN** a `VEVENT` carries a `LOCATION`
- **THEN** the raw event's venue name and address are populated from it, and coordinates come
  only from the ingest geocoder

### Requirement: Meetup source
The system SHALL provide a Meetup source backed by the Meetup GraphQL API (`keywordSearch`
filtered to a 50-mile radius around the Chattanooga center), registered only when
`events_meetup_token` is set (sent as an OAuth2 bearer token), with `events_meetup_query` as an
optional keyword filter. Parsing SHALL keep only `Event` results that have an id and a start time,
coerce start times to UTC, prefix the group name onto the description when present, build the
address from the venue's address/city/state (falling back to the venue name), and emit addresses
only — never coordinates.

#### Scenario: Token gates registration
- **WHEN** the application starts without `events_meetup_token`
- **THEN** no Meetup source is registered and no Meetup requests occur

#### Scenario: Only dated Event results are kept
- **WHEN** a Meetup response mixes `Event` results with other result types and undated entries
- **THEN** only dated `Event` results become raw events, each linking its `eventUrl` and carrying
  the Meetup event id as source event id

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
SHALL compare stored upcoming events within the same UTC day pairwise and merge a pair when
their canonical keys — recomputed under the current normalization, since stored keys predate
normalization changes — are equal (the same evidence that merges fresh reports at tier 2), or
when the tier-3 matcher accepts the pair. On a merge the earlier-created row survives, the longer title is kept, links
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

#### Scenario: Reconciliation merges stale-key exact duplicates
- **WHEN** two stored events' titles normalize identically under the current normalization
  with starts in the same UTC hour, but their stored canonical keys predate that
  normalization and their locations do not agree (e.g. one address geocoded imprecisely)
- **THEN** the reconciliation pass merges them on recomputed key equality alone

### Requirement: Configurable ingest radius filter
Ingest SHALL drop a new event — storing no event row, tags, or link — when its address geocodes
to coordinates farther than a configurable radius (`events_ingest_max_miles`, default 100, miles
from the Chattanooga center at 35.0456, -85.3097) using a haversine distance computed at ingest
time. A non-positive setting value SHALL disable the filter entirely. Events with no address,
whose geocoding fails, or whose failure is already cached SHALL be kept and stored with a null
location — only a successful geocode beyond the radius causes a drop. The filter SHALL apply
only when an event is first created: existing events are merged normally regardless of
location, and a stored event is never retroactively removed by the filter. Each ingest batch
SHALL report the number of dropped events as a `skipped_far` count alongside `created` and
`merged` (present and zero when the filter is disabled), and dropped events SHALL be logged.

#### Scenario: Far event is dropped and counted
- **WHEN** the filter is set to 100 miles and a source reports a new event whose address
  geocodes to Memphis (roughly 300 miles from the Chattanooga center)
- **THEN** no event, tags, or link are stored and the batch stats report it in `skipped_far`

#### Scenario: Nearby event passes the filter
- **WHEN** the filter is set to 100 miles and a source reports a new event whose address
  geocodes to downtown Chattanooga
- **THEN** the event is created with its location, exactly as without the filter

#### Scenario: Unlocated events are kept
- **WHEN** the filter is enabled and a source reports a new event with no address or with an
  address that fails to geocode
- **THEN** the event is stored with a null location and is not counted in `skipped_far`

#### Scenario: Non-positive radius disables filtering
- **WHEN** `events_ingest_max_miles` is 0 and a source reports an event geocoding far away
- **THEN** the event is stored with its location and `skipped_far` is 0

#### Scenario: Merge path is exempt
- **WHEN** an event already stored is reported again and the filter is enabled
- **THEN** the report merges into the existing event normally, regardless of where the event or
  the report's address is located

### Requirement: Keyword topic tagging
The system SHALL tag each newly created event by case-insensitive keyword matching of its title
and description against a code-defined topic→keywords map (topics: music, food, arts, outdoors,
family, sports, tech, community, education, nightlife, cars). The `cars` topic SHALL match
automotive-event phrasing — at minimum the keywords "car show", "cruise-in", "cruise in",
"cars and coffee", "car meet", "hot rod", "classic car", "corvette", "mustang", "camaro", and
"auto show" — and SHALL NOT use the bare substring "car" (to avoid false positives such as
"carnival"). Tags SHALL be stored as rows in a `tags` table joined many-to-many to events, and an
event may carry zero or many tags.

#### Scenario: Title keywords produce tags
- **WHEN** an event titled "Live music and food trucks" is ingested
- **THEN** it is tagged `music` and `food`

#### Scenario: Car events are tagged cars
- **WHEN** an event titled "Ooltewah Cruise In @ Cambridge Square" is ingested
- **THEN** it is tagged `cars`

#### Scenario: Bare "car" substrings do not tag
- **WHEN** an event titled "Downtown Carnival" with no other automotive keywords is ingested
- **THEN** it is not tagged `cars`

#### Scenario: No keyword match means no tags
- **WHEN** an ingested event's title and description match no topic keywords
- **THEN** the event is stored with zero tags

### Requirement: Address geocoding with a permanent cache
Ingest SHALL resolve event addresses to coordinates via OpenStreetMap Nominatim, sending a
descriptive configurable User-Agent, and SHALL cache every lookup — including failures — in a
`geocode_cache` table recording when the lookup was last attempted. A successfully geocoded
address SHALL never be queried again; a failed address SHALL NOT be re-queried except by the
periodic failure retry (see "Geocode failure retry with event backfill"). When the full address
string yields no result, the geocoder SHALL retry with progressively simplified fallback
variants of the address before recording a failure: first the address with its leading
(venue-name) component stripped, then the locality tail (city, state, zip, country) alone —
each variant only when the address has enough comma-separated components for the
simplification to be meaningful, with duplicate variants skipped and total attempts per lookup
bounded. A network or service error SHALL abort the lookup without trying further variants.
Outbound Nominatim requests — including fallback attempts — SHALL be spaced at least a
configurable minimum interval apart (default 1 second, per the public service's usage policy;
a non-positive interval disables the wait), including when lookups are requested concurrently.
Geocoding failures SHALL NOT fail ingest: the event is stored without a location.

#### Scenario: Repeated address hits the cache
- **WHEN** two events at the same address are ingested
- **THEN** Nominatim is queried at most once for that address

#### Scenario: Failed lookups are cached
- **WHEN** an address previously failed to geocode and appears again during ingest
- **THEN** no new Nominatim request is made and the event remains unlocated

#### Scenario: Venue-prefixed address falls back to the street address
- **WHEN** an address like "O'Charley's on Riverside, 674 N Riverside Drive, Clarksville, TN,
  37040, United States" yields no result as a full string
- **THEN** the geocoder retries with the leading component stripped ("674 N Riverside Drive,
  Clarksville, TN, 37040, United States") and uses that result

#### Scenario: Unresolvable street falls back to the locality
- **WHEN** both the full address and the venue-stripped variant yield no result
- **THEN** the geocoder queries the locality tail (city, state, zip, country) and, if it
  resolves, uses the locality coordinates

#### Scenario: Fallback attempts are rate limited
- **WHEN** a lookup runs through multiple fallback variants
- **THEN** consecutive Nominatim requests are spaced at least the configured minimum interval
  apart, the same as distinct lookups

#### Scenario: Service errors do not cascade into fallbacks
- **WHEN** a Nominatim request fails with a network or HTTP error
- **THEN** the lookup resolves to a failure without issuing further fallback requests

#### Scenario: Ungecodable events still stored
- **WHEN** geocoding fails for a new event's address after all fallback variants
- **THEN** the event is created with a null location

#### Scenario: Burst of uncached addresses is rate limited
- **WHEN** multiple uncached addresses are geocoded back-to-back in one refresh cycle
- **THEN** consecutive Nominatim requests are sent at least the configured minimum interval
  apart (1 second by default)

#### Scenario: Throttle disabled for a self-hosted instance
- **WHEN** the minimum interval setting is 0
- **THEN** requests are sent without any inter-request delay

### Requirement: Geocode failure retry with event backfill
Each refresh cycle SHALL, after source ingest and under the same refresh serialization, re-attempt
geocoding for a bounded batch of cached failures: up to `events_geocode_retry_batch` (default 25)
`geocode_cache` rows without coordinates whose last attempt is older than
`events_geocode_retry_hours` (default 24), oldest last-attempt first. A non-positive
`events_geocode_retry_hours` SHALL disable the retry pass. On a successful re-attempt the system
SHALL store the coordinates on the cache row and SHALL set the location of every stored event
whose address matches the cached address and whose location is null; backfilled events SHALL NOT
be dropped by the ingest radius filter. On a failed re-attempt the system SHALL update the row's
last-attempt time so the address is not retried again within the age window. The refresh result
SHALL report how many failures were retried and how many resolved.

#### Scenario: Stale failure is retried and heals its events
- **WHEN** a cached failure older than the retry age re-attempts and now geocodes successfully
- **THEN** the cache row gains the coordinates and every stored event with that address and a
  null location gets its location set — without waiting for a source to re-report the event

#### Scenario: Fresh failures wait out the age window
- **WHEN** an address failed to geocode less than `events_geocode_retry_hours` ago
- **THEN** the retry pass does not re-attempt it

#### Scenario: Failed retry defers the next attempt
- **WHEN** a retried address fails to geocode again
- **THEN** its last-attempt time is updated and it is not retried again until another full age
  window passes

#### Scenario: Retry volume is capped per cycle
- **WHEN** more stale failures exist than `events_geocode_retry_batch`
- **THEN** only the batch-size oldest are re-attempted this cycle and the rest wait for later
  cycles

#### Scenario: Retry pass can be disabled
- **WHEN** `events_geocode_retry_hours` is 0 or negative
- **THEN** no cached failure is ever re-attempted

#### Scenario: Successful lookups are never re-verified
- **WHEN** a cache row already has coordinates
- **THEN** the retry pass never re-queries it

#### Scenario: Pre-existing failures heal after deploy
- **WHEN** the system deploys over a database with failure rows created before the migration
- **THEN** those rows are immediately retry-eligible (their last-attempt time backfills from
  their creation time) and heal in subsequent refresh cycles with no manual intervention

### Requirement: Event storage with PostGIS location
Events SHALL be stored in Postgres in plain relational tables (not a hypertable) with timezone-aware
timestamps, and the event location SHALL be a nullable PostGIS point geometry (SRID 4326) with a
spatial index, created by a hand-written raw-SQL Alembic migration. Events SHALL be retained
indefinitely — the system SHALL NOT purge past events.

#### Scenario: Migration creates the schema
- **WHEN** `alembic upgrade head` runs on a database at revision 0002
- **THEN** the events, event_links, tags, event_tags, and geocode_cache tables exist, and the
  migration's downgrade removes them

#### Scenario: Past events persist
- **WHEN** an event's start time is long past
- **THEN** its row still exists and remains retrievable with `upcoming=false`

### Requirement: Scheduled refresh with serialized manual trigger
The system SHALL run an ingest cycle (fetch all registered sources, then upsert) as a scheduled
background job on a configurable interval (`events_refresh_minutes`, default 60), immediately once
at startup, gated by an `events_enabled` setting (default true). Scheduled and manual refreshes
SHALL be serialized so two cycles never run concurrently.

#### Scenario: Disabled feature schedules nothing
- **WHEN** the application starts with `events_enabled=false`
- **THEN** no events refresh job is scheduled

#### Scenario: Concurrent refreshes are serialized
- **WHEN** a manual refresh is requested while the scheduled cycle is running
- **THEN** the manual refresh waits for the running cycle rather than interleaving with it

### Requirement: Events listing API
The system SHALL serve `GET /api/v1/events/items` returning matching events ordered by start time
with count and the distance origin. Each item SHALL include title, description, start/end times,
venue name, address, latitude/longitude (null when unlocated), sorted tag names, all source links,
and `distance_miles` from the origin (null when unlocated). Filters SHALL be: repeatable `topic`
(events carrying any requested tag), `max_miles` with optional `lat`/`lon` origin (defaulting to
the Chattanooga center; when bounded, unlocated events are excluded), `upcoming` (default true —
only events starting at or after now), case-insensitive `search` on the title, and a result
`limit` (default 500). Distance filtering SHALL be computed in SQL against the PostGIS geometry.

#### Scenario: Default listing is upcoming events
- **WHEN** a client requests `GET /api/v1/events/items` with no parameters
- **THEN** only events starting at or after the current time are returned, ordered by start time,
  with distances measured from the Chattanooga center

#### Scenario: Distance filter excludes far and unlocated events
- **WHEN** a client requests `?max_miles=15`
- **THEN** events farther than 15 miles from the origin and events without coordinates are
  excluded, and returned items include `distance_miles`

#### Scenario: Topic filter matches any requested tag
- **WHEN** a client requests `?topic=music&topic=food`
- **THEN** exactly the events tagged `music` or `food` (or both) are returned

#### Scenario: Title search
- **WHEN** a client requests `?search=jazz`
- **THEN** only events whose title contains "jazz" case-insensitively are returned

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
