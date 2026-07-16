## ADDED Requirements

### Requirement: CitySpark events source
The system SHALL ingest The Pulse's CitySpark events calendar via its JSON API,
`POST https://portal.cityspark.com/api/events/GetEvents/<slug>`, sending a JSON body carrying the
portal id, an ISO start and end, a radius in miles with an origin latitude/longitude, and a `skip`
offset. The source SHALL be gated by an enable setting and SHALL expose its portal id/slug, radius,
and lookahead window as configuration, defaulting to the portal's own 25-mile radius around
`CHATTANOOGA_CENTER` and a 14-day lookahead. Requests SHALL NOT require or send authentication,
referer, or a spoofed browser User-Agent. Parsing SHALL be a pure function of the API payload so it
is testable offline with no network.

The source SHALL read event start and end times from the payload's `StartUTC`/`EndUTC` fields and
SHALL NOT read `DateStart`/`DateEnd`: the latter carry a `Z` suffix on values that are actually
venue-local time, so using them would shift every event by the UTC offset and corrupt the
`canonical_key` de-duplication hash. An event without `StartUTC` SHALL be skipped with a warning
rather than falling back to `DateStart`.

The source SHALL supply each event's `latitude`/`longitude` and its resolved tag names on the
`RawEvent`, so that ingest neither geocodes nor keyword-tags these events. Tag names SHALL be
resolved by mapping the event's integer tag ids against the payload's tag vocabulary (`AllTags`,
entries of `{id, name, parent}`), using each tag's own leaf name without rolling up to hierarchy
roots. Unmappable tag ids SHALL be skipped rather than failing the event.

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

#### Scenario: Tag ids resolve to their own leaf names
- **WHEN** an event carries tag ids that map to "Live Music" and "Food & Drink" in the payload's tag
  vocabulary
- **THEN** the raw event carries those tag names, not their hierarchy root names

#### Scenario: Unmappable tag id is skipped
- **WHEN** an event carries a tag id absent from the payload's tag vocabulary
- **THEN** that id contributes no tag and the event is still emitted with its remaining tags

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
configuration-gated sources (iCal feeds via `events_ical_feeds`, Meetup via its token, CitySpark via
its enable setting) remain overridable or removable through configuration alone, and the
CarCruiseFinder scraper is registered unconditionally (no per-source flag; removable only by code
change — its fragility is contained by per-source failure isolation rather than a switch). The
shipped configuration defaults therefore register exactly three sources: the Tennessee car-events
iCal feed, the CarCruiseFinder scraper, and the CitySpark calendar. No sample/fixture source SHALL
be importable by the application (fixtures live in the test suite only). Adding a source MUST
require only a new source class plus its registration — no changes to ingest, storage, API, or
frontend.

#### Scenario: Explicitly emptied configuration leaves only the always-on scraper
- **WHEN** a refresh cycle runs with `events_ical_feeds` set to an empty string, CitySpark disabled,
  and no tokens configured
- **THEN** the registry contains only the CarCruiseFinder source and the cycle completes
  successfully

#### Scenario: Sources supply what they know, and the pipeline derives the rest
- **WHEN** a source reports an event carrying coordinates and tags
- **THEN** those coordinates and tags are used as reported, and the event is neither geocoded nor
  keyword tagged

#### Scenario: Address-only sources are unaffected
- **WHEN** a source reports an event with a venue name and street address but no coordinates and no
  tags
- **THEN** coordinates are derived by the ingest pipeline's geocoder and topics by keyword tagging,
  exactly as before the coordinate and tag fields existed

### Requirement: Keyword topic tagging
The system SHALL tag each newly created event that its source did not supply tags for, by
case-insensitive keyword matching of its title and description against a code-defined
topic→keywords map (topics: music, food, arts, outdoors, family, sports, tech, community,
education, nightlife, cars). The `cars` topic SHALL match automotive-event phrasing — at minimum
the keywords "car show", "cruise-in", "cruise in", "cars and coffee", "car meet", "hot rod",
"classic car", "corvette", "mustang", "camaro", and "auto show" — and SHALL NOT use the bare
substring "car" (to avoid false positives such as "carnival"). When a source supplies tags, those
tags SHALL be used as reported and keyword matching SHALL NOT be applied to that event.
Source-supplied tag names SHALL be lowercased before storage so they merge with the keyword topic
vocabulary rather than creating case-variant duplicates in the unique, case-sensitive `tags` table.
Tags SHALL be stored as rows in a `tags` table joined many-to-many to events, and an event may carry
zero or many tags. Tag creation SHALL be idempotent under concurrent ingest.

#### Scenario: Title keywords produce tags
- **WHEN** an event titled "Live music and food trucks" with no source-supplied tags is ingested
- **THEN** it is tagged `music` and `food`

#### Scenario: Car events are tagged cars
- **WHEN** an event titled "Ooltewah Cruise In @ Cambridge Square" with no source-supplied tags is
  ingested
- **THEN** it is tagged `cars`

#### Scenario: Bare "car" substrings do not tag
- **WHEN** an event titled "Downtown Carnival" with no other automotive keywords and no
  source-supplied tags is ingested
- **THEN** it is not tagged `cars`

#### Scenario: No keyword match means no tags
- **WHEN** an ingested event has no source-supplied tags and its title and description match no
  topic keywords
- **THEN** the event is stored with zero tags

#### Scenario: Source-supplied tags replace keyword tagging
- **WHEN** an event titled "Live music at the pier" arrives with source-supplied tags
  `["Performing Arts"]`
- **THEN** it is tagged `performing arts` only, and is not tagged `music`

#### Scenario: Supplied tag names merge with the keyword vocabulary
- **WHEN** an event arrives with a source-supplied tag `"Music"` and the `music` tag already exists
  from keyword tagging
- **THEN** the event is linked to the existing `music` tag and no separate `Music` tag row is
  created

### Requirement: Address geocoding with a permanent cache
Ingest SHALL resolve the addresses of events whose source supplied no coordinates to coordinates via
OpenStreetMap Nominatim, sending a descriptive configurable User-Agent, and SHALL cache every lookup
— including failures — in a `geocode_cache` table recording when the lookup was last attempted. An
event whose source supplied coordinates SHALL NOT be geocoded and SHALL NOT consult or populate the
cache. A successfully geocoded address SHALL never be queried again; a failed address SHALL NOT be
re-queried except by the periodic failure retry (see "Geocode failure retry with event backfill").
When the full address string yields no result, the geocoder SHALL retry with progressively
simplified fallback variants of the address before recording a failure: first the address with its
leading (venue-name) component stripped, then the locality tail (city, state, zip, country) alone —
each variant only when the address has enough comma-separated components for the simplification to
be meaningful, with duplicate variants skipped and total attempts per lookup bounded. A network or
service error SHALL abort the lookup without trying further variants. Outbound Nominatim requests —
including fallback attempts — SHALL be spaced at least a configurable minimum interval apart
(default 1 second, per the public service's usage policy; a non-positive interval disables the
wait), including when lookups are requested concurrently. Geocoding failures SHALL NOT fail ingest:
the event is stored without a location.

#### Scenario: Source-supplied coordinates skip the geocoder
- **WHEN** an event whose source supplied coordinates is ingested
- **THEN** no Nominatim request is made for it, no `geocode_cache` row is written for its address,
  and the event is stored at the supplied coordinates

#### Scenario: Repeated address hits the cache
- **WHEN** two events at the same address, neither carrying source-supplied coordinates, are
  ingested
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
