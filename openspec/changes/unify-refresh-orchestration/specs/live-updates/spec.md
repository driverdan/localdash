## MODIFIED Requirements

### Requirement: Update signals are emitted at refresh choke points
Each feature's update signal SHALL be emitted from the code path shared by its scheduled and
manual refresh triggers, so a debug-panel or API-triggered refresh produces the same client
updates as a scheduled one. The signal decision SHALL be made inside that shared refresh entry
point, together with the cycle's serialization and its database session (if any). The scheduler
SHALL only invoke the entry point and SHALL NOT decide whether a signal is sent.

- **timeseries**: each collection cycle with a non-empty diff broadcasts that diff (scheduled tick and `POST /api/v1/timeseries/sources/{key}/refresh` share the same run path).
- **news**: every completed fetch+recluster cycle broadcasts a `news` ping (reclustering makes precise change detection unreliable; the ping cost is one client refetch per cycle).
- **events**: a cycle broadcasts an `events` ping only when it changed data — any created, merged, geocode-resolved, or reconciled count is nonzero; an unchanged cycle broadcasts nothing.
- **weather**: the scheduled weather refresh broadcasts a `weather` ping when the shaped payload differs from the payload the previous scheduled weather refresh produced; a failed refresh broadcasts nothing.

#### Scenario: Manual refresh signals like a scheduled one
- **WHEN** a client POSTs a manual news or events refresh and the cycle completes
- **THEN** the same update ping is broadcast as if the scheduled job had run the cycle

#### Scenario: Unchanged events cycle is silent
- **WHEN** an events refresh cycle completes with zero created, merged, geocode-resolved, and reconciled counts
- **THEN** no `events` ping is broadcast

#### Scenario: Empty timeseries diff is silent
- **WHEN** a collection cycle produces no new, updated, or closed entities
- **THEN** no `timeseries` message is broadcast

#### Scenario: Unchanged weather refresh is silent
- **WHEN** two consecutive scheduled weather refreshes produce equal payloads
- **THEN** only the first broadcasts a `weather` ping

#### Scenario: Weather change made by a request-driven refresh is still signalled
- **WHEN** a client request refreshes the expired weather cache with a new payload between two
  scheduled refreshes, and the next scheduled refresh returns that same payload
- **THEN** that scheduled refresh broadcasts a `weather` ping, because its payload differs from
  the one the previous scheduled refresh produced
