## MODIFIED Requirements

### Requirement: AGENTS.md matches the shipped app

The `AGENTS.md` guidance file SHALL reflect the current set of features and geo
collectors so agents onboarding from it receive accurate context. It SHALL also
state the backend code conventions that new modules are expected to follow.

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

#### Scenario: Backend code conventions are stated

- **WHEN** an agent reads `AGENTS.md` before adding a backend module or event source
- **THEN** it states that modules log through `logging.getLogger(__name__)`, so
  logger names are module paths (e.g. `app.events.sources.tribe`) rather than
  hand-written strings
- **AND** it states that an event source keeps its pure parsing in module-level
  functions that take what they need as arguments, which `fetch()` calls and tests
  import directly
- **AND** every module under `app/` that creates a logger follows the first rule,
  and every event source under `app/events/sources/` follows the second
