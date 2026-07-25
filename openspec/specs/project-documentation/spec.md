# project-documentation Specification

## Purpose

The canonical entry-point documentation — `README.md` (orienting someone new to
the project) and `AGENTS.md` (for coding agents) — must accurately describe the
app that actually ships: its user-facing features and the routes they serve, and
every built-in geo source. These requirements make documentation accuracy a
stated obligation so that when features, sources, or routes change, the docs are
updated in the same change rather than drifting behind the code.

The README is scoped to orientation. Contributor mechanics live in
`CONTRIBUTING.md` (see the `contributor-documentation` capability), architecture
and workflow live in `AGENTS.md`, and the API reference is the interactive
documentation the app itself serves — each with exactly one home, so no copy can
go stale.

## Requirements

### Requirement: README reflects current features and routes

The `README.md` SHALL describe LocalDash as a multi-feature local-data dashboard,
enumerating every user-facing feature that ships in the app together with the route
each is served at. When a feature is added or removed, or its route changes, the
README SHALL be updated in the same change.

#### Scenario: All shipped features are documented with their routes

- **WHEN** a reader opens `README.md`
- **THEN** it describes the Home digest page at `/`, the News feature at `/news`,
  the Timeseries map at `/map`, and the Events feature at `/events`
- **AND** it describes the Weather feature and where it surfaces
- **AND** it does not claim the News feed or the map dashboard is served at `/`

#### Scenario: A newly added feature is reflected

- **WHEN** a change adds a new user-facing feature and its route
- **THEN** the README is updated to list that feature and route

#### Scenario: Non-collector features are described as siblings

- **WHEN** a reader consults the README's description of the News, Events, or
  Weather features
- **THEN** none of them is presented as a geo collector or as flowing through the
  collector/ingest path

### Requirement: README lists all built-in geo sources

The `README.md` SHALL list every geo collector registered in
`app/collectors/__init__.py`'s `build_collectors()`, identified by its
human-readable name, and SHALL NOT list any feature that is not a registered
collector as a geo source.

#### Scenario: Every registered collector appears

- **WHEN** a reader consults the README's list of built-in sources
- **THEN** it includes Hamilton County TN 911 (`hc911`), TDOT SmartWay (`tdot`),
  EPB Outages (`epb`), and TN American Water Advisories (`tnaw`)

#### Scenario: Weather is not listed as a geo source

- **WHEN** a reader consults the README's list of built-in geo sources
- **THEN** Weather does not appear in it, because no weather collector is
  registered in `build_collectors()`

### Requirement: README is scoped to newcomer orientation

The `README.md` SHALL be written for a reader new to the project who wants to
understand what LocalDash is and run it. Contributor-facing material — development
environment setup, running tests, linting, architecture internals, and the git
workflow — SHALL NOT be duplicated in the README; the README SHALL link to the
document that owns each instead.

#### Scenario: Contributor setup is linked, not duplicated

- **WHEN** a reader looks for how to set up a development environment, run tests,
  or run the linters
- **THEN** the README links to `CONTRIBUTING.md` rather than restating those steps

#### Scenario: Architecture internals are linked, not duplicated

- **WHEN** a reader looks for the database schema, the collector base class, or how
  to add a data source
- **THEN** the README links to `AGENTS.md` rather than restating them
- **AND** the README contains no table of database tables and no collector code
  sample

#### Scenario: Git workflow is not restated

- **WHEN** a reader searches the README for branch naming, pull request process, or
  the OpenSpec three-PR lifecycle
- **THEN** the README does not restate them and links to `AGENTS.md` instead

#### Scenario: The core idea is summarized

- **WHEN** a reader reads the README's explanation of how LocalDash works
- **THEN** it summarizes that each upstream feed is a snapshot and LocalDash builds
  the time-series itself
- **AND** it does not describe hypertable partitioning, PostGIS geometry columns,
  or JSONB property bags

### Requirement: README points at the served API reference

The `README.md` SHALL direct readers to the API documentation served by the running
app rather than restating the endpoint list. The README SHALL NOT contain a
hand-maintained table of API endpoints.

#### Scenario: Reader is pointed at the served docs

- **WHEN** a reader looks for the API reference in the README
- **THEN** it points at the interactive documentation the app serves at `/docs`

#### Scenario: No hand-maintained endpoint tables

- **WHEN** a reader scans the README
- **THEN** there is no per-feature table enumerating methods, paths, and query
  parameters

### Requirement: README states geographic scope

The `README.md` SHALL state that LocalDash currently ships sources for the
Chattanooga / Hamilton County, TN area and that support for other cities is
planned, so a reader can tell whether it applies to their location.

#### Scenario: Current scope and future direction are both stated

- **WHEN** a reader asks whether LocalDash works for their city
- **THEN** the README states that the built-in sources are Chattanooga /
  Hamilton County specific
- **AND** it states that multi-city support is planned

#### Scenario: Configurable presentation is noted

- **WHEN** a reader consults the README's configuration guidance
- **THEN** it notes that the site name and the center coordinate are configurable

### Requirement: README opens with a screenshot

The `README.md` SHALL include a screenshot of the running dashboard near the top,
stored in the repository so it renders without network access.

#### Scenario: Screenshot is present and self-hosted

- **WHEN** a reader opens `README.md`
- **THEN** a screenshot of the dashboard appears near the top
- **AND** it is referenced by a repository-relative path, not an external URL

### Requirement: README documents no settings that do not exist

Every configuration setting named in the `README.md` SHALL exist in
`app/config.py`.

#### Scenario: No ghost settings

- **WHEN** a reader searches the README for a named configuration setting
- **THEN** that setting is defined in `app/config.py`
- **AND** `X-Frontend-Auth` is not referenced anywhere in the README

### Requirement: AGENTS.md matches the shipped app

The `AGENTS.md` guidance file SHALL reflect the current set of features and geo
collectors so agents onboarding from it receive accurate context.

#### Scenario: Feature count and features are current

- **WHEN** an agent reads `AGENTS.md`
- **THEN** it describes the four features (Timeseries, News, Events, Weather),
  including an Events architecture note covering `app/events/`, its sources, and
  the `/api/v1/events` namespace
- **AND** it describes the Weather feature as having no DB tables and no
  scheduler job

#### Scenario: All collectors are listed

- **WHEN** an agent reads the geo-source description in `AGENTS.md`
- **THEN** the `tnaw` (TN American Water Advisories) collector is included alongside
  `hc911`, `tdot`, and `epb`
