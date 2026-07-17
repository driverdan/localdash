# events Specification (delta)

Only change: the distance origin / source-default coordinate moves from the feature-internal
`CHATTANOOGA_CENTER` constant to the shared app-level settings `center_lat`/`center_lon`
(env-overridable, defaulting to the same 35.0456, -85.3097). Behavior at defaults is unchanged;
the center becomes configurable where it was previously hardcoded.

## MODIFIED Requirements

### Requirement: Meetup source
The system SHALL provide a Meetup source backed by the Meetup GraphQL API (`keywordSearch`
filtered to a 50-mile radius around the configured center, `center_lat`/`center_lon`), registered
only when `events_meetup_token` is set (sent as an OAuth2 bearer token), with
`events_meetup_query` as an optional keyword filter. Parsing SHALL keep only `Event` results that
have an id and a start time, coerce start times to UTC, prefix the group name onto the
description when present, build the address from the venue's address/city/state (falling back to
the venue name), and emit addresses only — never coordinates.

#### Scenario: Token gates registration
- **WHEN** the application starts without `events_meetup_token`
- **THEN** no Meetup source is registered and no Meetup requests occur

#### Scenario: Only dated Event results are kept
- **WHEN** a Meetup response mixes `Event` results with other result types and undated entries
- **THEN** only dated `Event` results become raw events, each linking its `eventUrl` and carrying
  the Meetup event id as source event id

### Requirement: CitySpark events source
The system SHALL ingest The Pulse's CitySpark events calendar via its JSON API,
`POST https://portal.cityspark.com/api/events/GetEvents/<slug>`, sending a JSON body carrying the
portal id, an ISO start and end, a radius in miles with an origin latitude/longitude, and a `skip`
offset. The source SHALL be gated by an enable setting and SHALL expose its portal id/slug, radius,
and lookahead window as configuration, defaulting to the portal's own 25-mile radius around the
configured center (`center_lat`/`center_lon`) and a 14-day lookahead. Requests SHALL NOT require
or send authentication, referer, or a spoofed browser User-Agent. Parsing SHALL be a pure function
of the API payload so it is testable offline with no network.

The source SHALL read event start and end times from the payload's `StartUTC`/`EndUTC` fields and
SHALL NOT read `DateStart`/`DateEnd`: the latter carry a `Z` suffix on values that are actually
venue-local time, so using them would shift every event by the UTC offset and corrupt the
`canonical_key` de-duplication hash. An event without `StartUTC` SHALL be skipped with a warning
rather than falling back to `DateStart`.

The source SHALL supply each event's `latitude`/`longitude` and its resolved tag names on the
`RawEvent`, so that ingest neither geocodes nor keyword-tags these events. Tag names SHALL be
resolved against the payload's tag hierarchy (`AllTags`, entries of `{id, name, parent}`, where a
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
Ingest SHALL drop a new event — storing no event row, tags, or link — when its address geocodes
to coordinates farther than a configurable radius (`events_ingest_max_miles`, default 100, miles
from the configured center `center_lat`/`center_lon`, default 35.0456, -85.3097) using a
haversine distance computed at ingest time. A non-positive setting value SHALL disable the filter
entirely. Events with no address, whose geocoding fails, or whose failure is already cached SHALL
be kept and stored with a null location — only a successful geocode beyond the radius causes a
drop. The filter SHALL apply only when an event is first created: existing events are merged
normally regardless of location, and a stored event is never retroactively removed by the filter.
Each ingest batch SHALL report the number of dropped events as a `skipped_far` count alongside
`created` and `merged` (present and zero when the filter is disabled), and dropped events SHALL
be logged.

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

### Requirement: Events listing API
The system SHALL serve `GET /api/v1/events/items` returning matching events ordered by start time
with count and the distance origin. Each item SHALL include title, description, start/end times,
venue name, address, latitude/longitude (null when unlocated), sorted tag names, all source links,
and `distance_miles` from the origin (null when unlocated). Filters SHALL be: repeatable `topic`
(events carrying any requested tag), `max_miles` with optional `lat`/`lon` origin (defaulting to
the configured center, `center_lat`/`center_lon`; when bounded, unlocated events are excluded),
`upcoming` (default true — only events starting at or after now), case-insensitive `search` on
the title, and a result `limit` (default 500). Distance filtering SHALL be computed in SQL
against the PostGIS geometry.

#### Scenario: Default listing is upcoming events
- **WHEN** a client requests `GET /api/v1/events/items` with no parameters
- **THEN** only events starting at or after the current time are returned, ordered by start time,
  with distances measured from the configured center

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

#### Scenario: Overridden center moves the default origin
- **WHEN** the app runs with `center_lat`/`center_lon` overridden via environment and a client
  requests `GET /api/v1/events/items` with no `lat`/`lon`
- **THEN** `distance_miles` and any `max_miles` filtering are measured from the overridden center
