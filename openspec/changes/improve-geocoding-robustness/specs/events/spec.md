## MODIFIED Requirements

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

## ADDED Requirements

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
