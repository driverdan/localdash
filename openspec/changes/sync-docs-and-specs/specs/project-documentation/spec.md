## MODIFIED Requirements

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
