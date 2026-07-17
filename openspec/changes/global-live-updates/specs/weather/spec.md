## MODIFIED Requirements

### Requirement: Response caching and staleness
The proxied payload SHALL be cached in-process with a TTL of `weather_cache_minutes` (default
10), with concurrent requests coalesced so parallel page loads trigger at most one upstream
refresh. On upstream failure, a previously cached payload SHALL be served as-is (its embedded
timestamps marking its age) rather than erroring; with no cached payload the endpoint SHALL
return 502. The forecast and observation fetches SHALL fail independently: if exactly one
succeeds, the response carries that half with the other `null` / empty. In addition to
lazy on-request refresh, a scheduled background job (gated by `weather_enabled`, interval
`weather_cache_minutes`) SHALL proactively refresh the cache so the payload stays current without
client requests, and SHALL broadcast a `weather` update ping on the global live-update bus (see
`live-updates`) when the shaped payload differs from the previously cached one; a failed proactive
refresh SHALL log, keep the stale payload, and broadcast nothing.

#### Scenario: Requests within the TTL hit the cache
- **WHEN** two requests arrive within `weather_cache_minutes` of a successful refresh
- **THEN** the second is served from cache with no upstream calls

#### Scenario: Stale payload served on upstream failure
- **WHEN** the cache TTL has expired, a refresh attempt fails, and a previous payload is cached
- **THEN** the endpoint returns the previous payload successfully

#### Scenario: Cold failure returns 502
- **WHEN** the first request after startup fails to fetch from NWS
- **THEN** the endpoint returns 502 and the next request retries upstream

#### Scenario: Partial upstream failure yields a partial response
- **WHEN** the observation fetch fails but the forecast fetch succeeds
- **THEN** the response carries the forecast periods with `current` null

#### Scenario: Proactive refresh pings on change
- **WHEN** the scheduled weather job refreshes the cache and the shaped payload differs from the
  previous one
- **THEN** a `{topic: "weather", type: "updated"}` message is broadcast on `/api/v1/ws`

#### Scenario: Failed proactive refresh is silent
- **WHEN** the scheduled weather job's upstream refresh fails
- **THEN** the previous payload remains cached and no `weather` ping is broadcast
