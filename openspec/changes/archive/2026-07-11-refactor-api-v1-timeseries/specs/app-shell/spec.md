## ADDED Requirements

### Requirement: Versioned feature-namespaced API surface
All API routes SHALL live under the `/api/v1` prefix, and every feature SHALL own its own namespace under `/api/v1/<feature>/` (e.g., `/api/v1/timeseries/`). Feature-agnostic endpoints live directly under `/api/v1`. Adding a feature SHALL NOT require modifying another feature's routes — each feature is a self-contained router composed in the application entrypoint.

#### Scenario: Feature routes are namespaced
- **WHEN** a feature exposes an endpoint
- **THEN** its path begins with `/api/v1/<feature>/` and no feature serves routes inside another feature's namespace

#### Scenario: Static frontend does not shadow the API
- **WHEN** a client requests any `/api/...` path
- **THEN** the API router handles it (the static file mount only serves paths outside `/api`)

### Requirement: App bootstrap config endpoint
The system SHALL serve global frontend bootstrap configuration at `GET /api/v1/config`, including at least the map tile URL and tile attribution. This endpoint is feature-agnostic and SHALL remain outside any feature namespace.

#### Scenario: Fetching bootstrap config
- **WHEN** a client requests `GET /api/v1/config`
- **THEN** it receives `tile_url` and `tile_attribution` for initializing the UI
