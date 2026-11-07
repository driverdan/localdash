## MODIFIED Requirements

### Requirement: Pluggable event source interface
The events feature SHALL define a pluggable source interface: a `RawEvent` value (title, start
time, source name, source URL, plus optional description, end time, venue name, address, source
event id, latitude/longitude, and tags) and an `EventSource` base class whose async `fetch()`
returns the source's current `RawEvent` list. A source SHALL supply the coordinates and tags it
already knows and SHALL omit those it does not; the ingest pipeline SHALL derive only what a source
omits — geocoding an address only when coordinates are absent, and keyword tagging only when tags
are absent. The coordinate and tag fields SHALL be optional, so a source that supplies neither
behaves exactly as before. Sources SHALL be registered in a single build function:
configuration-gated sources (iCal feeds via `events_ical_feeds`, The Events Calendar (tribe)
calendars via `events_tribe_calendars`, Meetup via its token, CitySpark via its enable setting)
remain overridable or removable through configuration alone, and the CarCruiseFinder and
Chattanooga Zoo scrapers are registered unconditionally (no per-source flag; removable only by code
change — their fragility is contained by per-source failure isolation rather than a switch). The
shipped configuration defaults therefore register exactly five sources: the CarCruiseFinder
scraper, the Chattanooga Zoo scraper, the CitySpark calendar, the Tennessee car-events iCal feed,
and the Chattanooga Public Library tribe calendar. No sample/fixture source SHALL
be importable by the application (fixtures live in the test suite only). Adding a source MUST
require only a new source class plus its registration — no changes to ingest, storage, API, or
frontend.

#### Scenario: Shipped defaults register five sources
- **WHEN** sources are built from the default configuration
- **THEN** the registry contains exactly the CarCruiseFinder, Chattanooga Zoo, CitySpark, Tennessee
  car-events iCal, and Chattanooga Public Library tribe sources

#### Scenario: Explicitly emptied configuration leaves only the always-on scrapers
- **WHEN** a refresh cycle runs with `events_ical_feeds` and `events_tribe_calendars` set to empty
  strings, CitySpark disabled, and no tokens configured
- **THEN** the registry contains only the CarCruiseFinder and Chattanooga Zoo sources and the cycle
  completes successfully

#### Scenario: Sources supply what they know, and the pipeline derives the rest
- **WHEN** a source reports an event carrying coordinates and tags
- **THEN** those coordinates and tags are used as reported, and the event is neither geocoded nor
  keyword tagged

#### Scenario: Address-only sources are unaffected
- **WHEN** a source reports an event with a venue name and street address but no coordinates and no
  tags
- **THEN** coordinates are derived by the ingest pipeline's geocoder and topics by keyword tagging,
  exactly as before the coordinate and tag fields existed

### Requirement: CitySpark events source
The system SHALL ingest The Pulse's CitySpark events calendar via its JSON API. Each run SHALL
first request the portal's widget bootstrap, `GET https://portal.cityspark.com/PortalScripts/<slug>`,
and read the tag vocabulary (`AllTags`) from it, then page through
`POST https://portal.cityspark.com/api/events/GetEvents/<slug>`, sending a JSON body carrying the
portal id, an ISO start and end, a radius in miles with an origin latitude/longitude, and a `skip`
offset. Paging SHALL use pages of 100 events, stop at the first short page, and stop after at most
20 pages so a misbehaving API cannot page forever. The source SHALL be gated by an enable setting and SHALL expose its portal id/slug, radius,
and lookahead window as configuration, defaulting to the portal's own 25-mile radius around the
configured center (`center_lat`/`center_lon`) and a 14-day lookahead. Requests SHALL NOT require or send authentication,
referer, or a spoofed browser User-Agent. Parsing SHALL be a pure function of the API payload so it
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

### Requirement: Configurable ingest radius filter
Ingest SHALL drop a new event — storing no event row, tags, or link — when its coordinates,
whether supplied by the source or geocoded from its address, lie farther than a configurable radius (`events_ingest_max_miles`, default 100, miles
from the configured center `center_lat`/`center_lon`, default 35.0456, -85.3097) using a
haversine distance computed at ingest time. A non-positive setting value SHALL disable the filter entirely. Events with no
source-supplied coordinates and no address, whose geocoding fails, or whose failure is already
cached SHALL be kept and stored with a null location — only known coordinates beyond the radius
cause a drop. The filter SHALL apply
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

#### Scenario: Far source-supplied coordinates are dropped
- **WHEN** the filter is set to 100 miles and a source reports a new event carrying its own
  coordinates roughly 300 miles from the center
- **THEN** the event is dropped and counted in `skipped_far`, without any geocoding lookup

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
