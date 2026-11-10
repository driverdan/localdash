## MODIFIED Requirements

### Requirement: README lists all built-in geo sources

The `README.md` SHALL list every geo collector registered in
`app/timeseries/collectors/__init__.py`'s `build_collectors()`, identified by its
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

### Requirement: AGENTS.md matches the shipped app

The `AGENTS.md` guidance file SHALL reflect the current set of features and geo
collectors so agents onboarding from it receive accurate context.

#### Scenario: Feature count and features are current

- **WHEN** an agent reads `AGENTS.md`
- **THEN** it describes the four features (Timeseries, News, Events, Weather),
  including an Events architecture note covering `app/events/`, its sources, and
  the `/api/v1/events` namespace
- **AND** it describes the Weather feature as having no DB tables, with a scheduled
  refresh job that keeps its in-process cache current and pings live clients

#### Scenario: All collectors are listed

- **WHEN** an agent reads the geo-source description in `AGENTS.md`
- **THEN** the `tnaw` (TN American Water Advisories) collector is included alongside
  `hc911`, `tdot`, and `epb`

#### Scenario: Timeseries module paths are current

- **WHEN** an agent follows a path `AGENTS.md` gives for the timeseries pipeline
  (collectors, ingest, models, the `Diff` type, GeoJSON helpers) or for the shared
  SQLAlchemy `Base`
- **THEN** the path names an existing module: the timeseries pipeline under
  `app/timeseries/` and `Base` in `app/orm.py`
- **AND** "Adding a data source" tells the agent to write the collector in
  `app/timeseries/collectors/<name>.py` and register it in
  `app/timeseries/collectors/__init__.py`'s `build_collectors()`
