## MODIFIED Requirements

### Requirement: CitySpark events source
The system SHALL ingest The Pulse's CitySpark events calendar via its JSON API. Each run SHALL
first request the portal's widget bootstrap, `GET https://portal.cityspark.com/PortalScripts/<slug>`,
and read the tag vocabulary (`AllTags`) from it, then page through
`POST https://portal.cityspark.com/api/events/GetEvents/<slug>`, sending a JSON body carrying the
portal id, an ISO start and end, a radius in miles with an origin latitude/longitude, and a `skip`
offset. Paging SHALL use pages of 100 events, stop at the first short page, and stop after at most
20 pages so a misbehaving API cannot page forever. The source SHALL be gated by an enable setting and SHALL expose its portal id/slug, radius,
and lookahead window as configuration, defaulting to the portal's own 25-mile radius around the
configured center (`center_lat`/`center_lon`) and a 14-day lookahead. Requests SHALL NOT require or send authentication
or a referer, and SHALL send the application's default User-Agent (the `user_agent` setting). Parsing SHALL be a pure function of the API payload so it
is testable offline with no network.

The source SHALL read event start and end times from the payload's `StartUTC`/`EndUTC` fields and
SHALL NOT read `DateStart`/`DateEnd`: the latter carry a `Z` suffix on values that are actually
venue-local time, so using them would shift every event by the UTC offset and corrupt the
`canonical_key` de-duplication hash. An event without `StartUTC` SHALL be skipped with a warning
rather than falling back to `DateStart`.

The source SHALL supply each event's `latitude`/`longitude` and its resolved tag names on the
`RawEvent`, so that ingest neither geocodes nor keyword-tags these events. Tag names SHALL be
resolved against the bootstrap's tag hierarchy (`AllTags`, entries of `{id, name, parent}`, where a
root has a null parent) by walking each of the event's tag ids to its root and taking the name of
the node **one level below that root**; a tag id that is itself a root SHALL resolve to its own
name. Several distinct tag ids on one event MAY resolve to the same name, in which case the event
SHALL carry that tag once. The walk SHALL terminate on a malformed hierarchy: a parent cycle SHALL
NOT hang, and a dangling parent id SHALL resolve to the deepest node actually reachable. Tag ids
absent from the vocabulary SHALL be skipped rather than failing the event. Rolling up is the
source's responsibility — ingest SHALL receive already-resolved names and SHALL NOT be aware of the
hierarchy.

#### Scenario: Start times are read from StartUTC, not DateStart
- **WHEN** an event payload carries `DateStart: "2026-07-15T08:00:00Z"` and
  `StartUTC: "2026-07-15T12:00:00Z"`
- **THEN** the raw event's start time is `2026-07-15T12:00:00+00:00`

#### Scenario: Event without StartUTC is skipped
- **WHEN** an event payload has no `StartUTC` value
- **THEN** the event is skipped with a warning and no raw event is emitted for it

#### Scenario: Paging continues until a short page
- **WHEN** the API returns full pages of 100 events for `skip` 0, 100, and a page of 26 at `skip` 200
- **THEN** the source issues no further requests and returns all 226 events

#### Scenario: Empty result yields zero events
- **WHEN** the API returns a successful response whose event list is empty
- **THEN** the source returns zero raw events without error

#### Scenario: Tag ids roll up to one level below their root
- **WHEN** an event carries the tag id for "Live Music", whose hierarchy chain is
  "Performing Arts > Music > Live Music"
- **THEN** the raw event carries the tag `music` — neither the leaf name `live music` nor the root
  name `performing arts`

#### Scenario: A root tag resolves to itself
- **WHEN** an event carries the tag id for "Nightlife", which is a root (null parent)
- **THEN** the raw event carries the tag `nightlife`

#### Scenario: Tags under one depth-1 node collapse to a single tag
- **WHEN** an event carries the tag ids for both "Live Music" and "MusicEvent", whose chains are
  "Performing Arts > Music > Live Music" and "Performing Arts > Music > MusicEvent"
- **THEN** the raw event carries the tag `music` exactly once

#### Scenario: Unmappable tag id is skipped
- **WHEN** an event carries a tag id absent from the payload's tag vocabulary
- **THEN** that id contributes no tag and the event is still emitted with its remaining tags

#### Scenario: Malformed hierarchy does not hang the rollup
- **WHEN** an event carries a tag id whose parent chain contains a cycle
- **THEN** the rollup terminates and the event is still emitted

#### Scenario: Coordinates and tags are supplied to ingest
- **WHEN** a CitySpark event with coordinates and tags is ingested
- **THEN** the stored event's location comes from the payload, no Nominatim request is made for it,
  and no keyword tagging is applied to it

#### Scenario: Broken source does not affect other sources
- **WHEN** the CitySpark API errors or returns an unparseable payload during a refresh cycle
- **THEN** the cycle logs the failure, ingests the other sources normally, and completes

#### Scenario: Disabled by configuration
- **WHEN** a refresh cycle runs with the CitySpark enable setting off
- **THEN** the registry contains no CitySpark source and no request is made to the CitySpark API

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
warning rather than failing startup. Requests SHALL NOT send authentication, and SHALL send the
application's default User-Agent (the `user_agent` setting). Parsing SHALL be a pure function of a page's JSON payload so it is testable offline
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

### Requirement: Chattanooga Zoo scraper source
The system SHALL provide a Chattanooga Zoo source that scrapes the zoo's events listing page
(`https://chattzoo.org/events/zooevents`) and the detail page of each event linked from it,
registered unconditionally as a normal event source in `build_sources()` (no per-source config
flag; the site publishes no machine endpoint — no iCal, feed, REST API, sitemap, JSON-LD,
microdata, or Open Graph tags — so HTML scraping is the only route, and that fragility is
contained by `run_sources()`'s existing per-source failure isolation, matching how
CarCruiseFinder is treated).

Fetching SHALL send the application's default User-Agent (the `user_agent` setting; the site
does not require any particular User-Agent) and SHALL follow redirects (the listing is served from
the apex domain and links to the `www.` host). The source SHALL request the listing page once
per run and then one detail page per listed event; unlike the CarCruiseFinder source, fetching
detail pages is required here because the listing page carries no dates at all, and it is safe
here because the zoo's detail pages carry no UTC offsets to be wrong.

Extraction SHALL take the image and detail URL from each listing card, and the occurrence
date/time strings and description from the linked detail page. The title SHALL be the detail
page's heading, falling back to the listing card's title when the detail page has none. Each raw event
SHALL carry the zoo's venue name, its full postal address, and its fixed coordinates supplied
directly by the source (so the source adds no geocoder load), the detail page URL as its
source link, and no tags (ingest's keyword tagger derives them).

#### Scenario: Registered as a normal source
- **WHEN** the application builds its event sources for a refresh cycle
- **THEN** a Chattanooga Zoo source is registered alongside the other configured event
  sources, with no additional setting required to enable it

#### Scenario: Listing cards are resolved to detail pages
- **WHEN** the listing page is fetched and contains event cards
- **THEN** the image URL and detail URL are taken from each card, and one request is made per
  distinct detail URL

#### Scenario: Detail page heading supplies the title
- **WHEN** a detail page has a heading and its listing card shows a different, shorter title
- **THEN** the raw event's title is the detail page's heading; a detail page without a heading
  falls back to the card's title

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
