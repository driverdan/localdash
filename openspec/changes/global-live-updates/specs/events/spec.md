## MODIFIED Requirements

### Requirement: Scheduled refresh with serialized manual trigger
The system SHALL run an ingest cycle (fetch all registered sources, then upsert) as a scheduled
background job on a configurable interval (`events_refresh_minutes`, default 60), immediately once
at startup, gated by an `events_enabled` setting (default true). Scheduled and manual refreshes
SHALL be serialized so two cycles never run concurrently. A cycle that changed data — any of its
created, merged, geocode-resolved, or reconciled counts is nonzero — SHALL broadcast an `events`
update ping on the global live-update bus (see `live-updates`), from the code path shared by the
scheduled job and the manual refresh so both trigger it identically; a cycle with all such counts
zero SHALL broadcast nothing.

#### Scenario: Disabled feature schedules nothing
- **WHEN** the application starts with `events_enabled=false`
- **THEN** no events refresh job is scheduled

#### Scenario: Concurrent refreshes are serialized
- **WHEN** a manual refresh is requested while the scheduled cycle is running
- **THEN** the manual refresh waits for the running cycle rather than interleaving with it

#### Scenario: Changed cycle emits update ping
- **WHEN** a refresh cycle completes having created or merged at least one event
- **THEN** a `{topic: "events", type: "updated"}` message is broadcast on `/api/v1/ws`

#### Scenario: Unchanged cycle is silent
- **WHEN** a refresh cycle completes with zero created, merged, geocode-resolved, and reconciled
  counts
- **THEN** no `events` ping is broadcast
