## MODIFIED Requirements

### Requirement: Global live-update WebSocket endpoint
The system SHALL expose a single feature-agnostic WebSocket endpoint at `/api/v1/ws` that carries live-update messages for all features. Every connected client SHALL receive every broadcast message (no per-client topic or source filtering); clients filter by message content. A client that disconnects (including mid-send failures) SHALL be dropped from the broadcast set without affecting delivery to other clients.

#### Scenario: One connection serves all features
- **WHEN** a client is connected to `/api/v1/ws` and a timeseries poll cycle, a news cycle, and an events cycle each produce updates
- **THEN** the client receives a message for each over the same connection

#### Scenario: Broken client does not break broadcast
- **WHEN** a broadcast is sent while one connected client's socket has failed
- **THEN** the remaining clients receive the message and the failed socket is removed from the broadcast set

#### Scenario: Closed client is removed
- **WHEN** a client connected to `/api/v1/ws` closes its socket
- **THEN** the endpoint removes that client from the broadcast set
- **AND** the close is not reported as an application error
