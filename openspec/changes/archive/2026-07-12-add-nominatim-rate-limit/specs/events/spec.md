## MODIFIED Requirements

### Requirement: Address geocoding with a permanent cache
Ingest SHALL resolve event addresses to coordinates via OpenStreetMap Nominatim, sending a
descriptive configurable User-Agent, and SHALL cache every lookup — including failures — in a
`geocode_cache` table so no address is ever geocoded twice. Outbound Nominatim requests SHALL
be spaced at least a configurable minimum interval apart (default 1 second, per the public
service's usage policy; a non-positive interval disables the wait), including when lookups
are requested concurrently. Geocoding failures SHALL NOT fail ingest: the event is stored
without a location.

#### Scenario: Repeated address hits the cache
- **WHEN** two events at the same address are ingested
- **THEN** Nominatim is queried at most once for that address

#### Scenario: Failed lookups are cached
- **WHEN** an address previously failed to geocode and appears again
- **THEN** no new Nominatim request is made and the event remains unlocated

#### Scenario: Ungecodable events still stored
- **WHEN** geocoding fails for a new event's address
- **THEN** the event is created with a null location

#### Scenario: Burst of uncached addresses is rate limited
- **WHEN** multiple uncached addresses are geocoded back-to-back in one refresh cycle
- **THEN** consecutive Nominatim requests are sent at least the configured minimum interval
  apart (1 second by default)

#### Scenario: Throttle disabled for a self-hosted instance
- **WHEN** the minimum interval setting is 0
- **THEN** requests are sent without any inter-request delay
