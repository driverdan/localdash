## ADDED Requirements

### Requirement: Scheduled refresh bypasses the cache TTL
Each tick of the scheduled weather job SHALL fetch upstream regardless of the cached payload's
age. The TTL check SHALL apply only to on-request refreshes. A tick that coincides with a
not-quite-expired cache SHALL still refresh, so the proactive refresh happens every
`weather_cache_minutes`. The forced refresh SHALL otherwise behave like any refresh: it is
coalesced under the same lock as request-driven refreshes, a failure keeps the stale payload, and
last-good AQI carry-forward still applies.

#### Scenario: Every job tick refreshes upstream
- **WHEN** the scheduled job ticks one interval after the previous refresh, while the cached
  payload's age is still marginally under the TTL
- **THEN** the job fetches fresh data from upstream instead of returning the cached payload

#### Scenario: Request path still honors the TTL
- **WHEN** a client requests `/api/v1/weather/current` within the TTL of the last refresh
- **THEN** the cached payload is served with no upstream calls
