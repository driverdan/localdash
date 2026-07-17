# live-updates Specification

## Purpose

The backend's global live-update WebSocket bus: the feature-agnostic `/api/v1/ws` endpoint
(`app/api/root.py`, connection management in `app/ws.py`), the topic-envelope message contract —
timeseries diffs as data messages, news/events/weather as payload-free invalidation pings — and the
rules for when each feature's refresh cycle emits a signal. Consumed by the `frontend-live`
capability's singleton client bus.

## Requirements

### Requirement: Global live-update WebSocket endpoint
The system SHALL expose a single feature-agnostic WebSocket endpoint at `/api/v1/ws` that carries live-update messages for all features. Every connected client SHALL receive every broadcast message (no per-client topic or source filtering); clients filter by message content. A client that disconnects (including mid-send failures) SHALL be dropped from the broadcast set without affecting delivery to other clients.

#### Scenario: One connection serves all features
- **WHEN** a client is connected to `/api/v1/ws` and a timeseries poll cycle, a news cycle, and an events cycle each produce updates
- **THEN** the client receives a message for each over the same connection

#### Scenario: Broken client does not break broadcast
- **WHEN** a broadcast is sent while one connected client's socket has failed
- **THEN** the remaining clients receive the message and the failed socket is removed from the broadcast set

### Requirement: Topic envelope message contract
Every message broadcast on `/api/v1/ws` SHALL be a JSON object carrying a `topic` field identifying the originating feature. Two message shapes SHALL exist:

- **Data messages** — `topic: "timeseries", type: "diff"` messages carry the full poll-cycle diff (`source`, `new`/`updated` GeoJSON features, `closed` entity ids) so clients can update incrementally without refetching.
- **Invalidation pings** — `topic: "news" | "events" | "weather", type: "updated"` messages carry no payload; they signal that the client's current data for that feature may be stale and SHALL be refreshed through the feature's existing REST endpoints.

#### Scenario: Timeseries diffs carry data
- **WHEN** a timeseries poll cycle produces a non-empty diff
- **THEN** clients receive `{topic: "timeseries", type: "diff", source, new, updated, closed}` with the affected features and ids inline

#### Scenario: Pings carry no data
- **WHEN** a news refresh cycle completes
- **THEN** clients receive `{topic: "news", type: "updated"}` with no story payload, and fetch fresh data via REST if they care

### Requirement: Update signals are emitted at refresh choke points
Each feature's update signal SHALL be emitted from the code path shared by its scheduled and manual refresh triggers, so a debug-panel or API-triggered refresh produces the same client updates as a scheduled one:

- **timeseries**: each collection cycle with a non-empty diff broadcasts that diff (scheduled tick and `POST /api/v1/timeseries/sources/{key}/refresh` share the same run path).
- **news**: every completed fetch+recluster cycle broadcasts a `news` ping (reclustering makes precise change detection unreliable; the ping cost is one client refetch per cycle).
- **events**: a cycle broadcasts an `events` ping only when it changed data — any created, merged, geocode-resolved, or reconciled count is nonzero; an unchanged cycle broadcasts nothing.
- **weather**: the scheduled weather refresh broadcasts a `weather` ping when the shaped payload differs from the previously cached payload.

#### Scenario: Manual refresh signals like a scheduled one
- **WHEN** a client POSTs a manual news or events refresh and the cycle completes
- **THEN** the same update ping is broadcast as if the scheduled job had run the cycle

#### Scenario: Unchanged events cycle is silent
- **WHEN** an events refresh cycle completes with zero created, merged, geocode-resolved, and reconciled counts
- **THEN** no `events` ping is broadcast

#### Scenario: Empty timeseries diff is silent
- **WHEN** a collection cycle produces no new, updated, or closed entities
- **THEN** no `timeseries` message is broadcast
