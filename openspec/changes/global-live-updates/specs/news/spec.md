## MODIFIED Requirements

### Requirement: Scheduled feed fetching with per-feed error isolation
The system SHALL fetch all enabled feeds on a configurable interval (default 15 minutes) as a
scheduled background job, and immediately once at startup. A feed that errors SHALL NOT abort the
cycle: the failure is caught per-feed and recorded on that feed's `last_status`, and every fetch
updates the feed's `last_fetch`/`last_status` telemetry. Requests SHALL send a mainstream browser
User-Agent string (TownNews-hosted feeds rate-limit unfamiliar UAs with HTTP 429). Scheduled and
manual refreshes SHALL be serialized so two refresh cycles never run concurrently. Every completed
fetch+recluster cycle SHALL broadcast a `news` update ping on the global live-update bus (see
`live-updates`), from the code path shared by the scheduled job and the manual refresh so both
trigger it identically; a failed cycle broadcasts nothing.

#### Scenario: One dead feed does not stop the others
- **WHEN** one feed returns an error during a refresh cycle
- **THEN** the remaining feeds are still fetched, and the failing feed's `last_status` records the
  error

#### Scenario: Concurrent refreshes are serialized
- **WHEN** a manual refresh is requested while the scheduled refresh is running
- **THEN** the manual refresh waits for the running cycle rather than interleaving with it

#### Scenario: Completed cycle emits update ping
- **WHEN** a scheduled or manual refresh cycle completes
- **THEN** a `{topic: "news", type: "updated"}` message is broadcast on `/api/v1/ws`
