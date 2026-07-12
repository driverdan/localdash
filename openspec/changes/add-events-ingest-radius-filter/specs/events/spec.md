## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Cross-source de-duplication on ingest
Ingest SHALL collapse the same real-world event reported by multiple sources onto one canonical
record keyed by a stable hash of the normalized title (lowercased, punctuation stripped,
whitespace collapsed) plus the UTC start day-and-hour. New keys create an event unless dropped
by the ingest radius filter; existing keys merge: empty description, venue name, and address
are backfilled from the incoming report, and a still-unlocated event is geocoded from the newly
available address. Each reporting source SHALL contribute one link per event (source name, URL,
source event id), unique per `(event, source_name)`, with the URL refreshed when the same
source reports again. A failure in one source SHALL NOT abort ingestion of the others.

#### Scenario: Same event from two sources merges
- **WHEN** two sources report "Jazz Night!" and "jazz night" with start times in the same UTC hour
- **THEN** one event row exists with two links, one per source

#### Scenario: Merge backfills missing fields
- **WHEN** an event was stored without an address and a second source reports it with one
- **THEN** the canonical event gains the address and is geocoded from it

#### Scenario: One failing source does not abort the cycle
- **WHEN** one registered source raises during fetch
- **THEN** events from the remaining sources are still ingested

#### Scenario: Repeat ingest is idempotent
- **WHEN** the same source reports the same events on consecutive cycles
- **THEN** no duplicate events or links are created

### Requirement: Tags and refresh API
The system SHALL serve `GET /api/v1/events/tags` returning all known tag names sorted, and
`POST /api/v1/events/refresh` which runs a full ingest cycle (serialized with the scheduled job)
and returns the created, merged, and skipped-far counts.

#### Scenario: Tags list
- **WHEN** a client requests `GET /api/v1/events/tags` after events tagged `music` and `arts` exist
- **THEN** the response contains `arts` and `music` in sorted order

#### Scenario: Manual refresh reports counts
- **WHEN** a client sends `POST /api/v1/events/refresh`
- **THEN** an ingest cycle runs and the response reports how many events were created and
  merged, and how many new far-away events were skipped by the ingest radius filter
