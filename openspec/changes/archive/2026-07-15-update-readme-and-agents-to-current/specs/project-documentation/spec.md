## ADDED Requirements

### Requirement: README reflects current features and routes

The `README.md` SHALL describe LocalDash as a multi-feature local-data dashboard,
enumerating every user-facing feature that ships in the app together with the route
each is served at. When a feature is added or removed, or its route changes, the
README SHALL be updated in the same change.

#### Scenario: All shipped features are documented with their routes

- **WHEN** a reader opens `README.md`
- **THEN** it describes the News feature at `/`, the Timeseries map at `/map`, and
  the Events feature at `/events`
- **AND** it does not claim the map dashboard is served at `/`

#### Scenario: A newly added feature is reflected

- **WHEN** a change adds a new user-facing feature and its route
- **THEN** the README is updated to list that feature and route

### Requirement: README lists all built-in geo sources

The `README.md` SHALL list every geo collector registered in
`app/collectors/__init__.py`'s `build_collectors()`, identified by its
human-readable name.

#### Scenario: Every registered collector appears

- **WHEN** a reader consults the README's list of built-in sources
- **THEN** it includes Hamilton County TN 911 (`hc911`), TDOT SmartWay (`tdot`),
  EPB Outages (`epb`), and TN American Water Advisories (`tnaw`)

### Requirement: README documents the current API surface

The `README.md` API reference SHALL document the versioned, feature-namespaced
routes actually served by the app, and SHALL NOT reference routes that no longer
exist.

#### Scenario: Documented routes match the served routes

- **WHEN** a reader follows the README's API reference
- **THEN** paths are under `/api/v1/` and grouped by feature namespace
  (`/api/v1/config`, `/api/v1/timeseries/*`, `/api/v1/news/*`, `/api/v1/events/*`)
- **AND** the timeseries WebSocket is documented at `/api/v1/timeseries/ws`

#### Scenario: Stale routes are absent

- **WHEN** a reader searches the README for flat, unversioned routes such as
  `/api/active`, `/api/ws/live`, or `/api/sources`
- **THEN** none are present

### Requirement: AGENTS.md matches the shipped app

The `AGENTS.md` guidance file SHALL reflect the current set of features and geo
collectors so agents onboarding from it receive accurate context.

#### Scenario: Feature count and Events feature are current

- **WHEN** an agent reads `AGENTS.md`
- **THEN** it describes the three features (News, Timeseries, Events), including an
  Events architecture note covering `app/events/`, its sources, and the
  `/api/v1/events` namespace

#### Scenario: All collectors are listed

- **WHEN** an agent reads the geo-source description in `AGENTS.md`
- **THEN** the `tnaw` (TN American Water Advisories) collector is included alongside
  `hc911`, `tdot`, and `epb`
