## ADDED Requirements

### Requirement: AGENTS.md identifies reserved source configuration columns

The `AGENTS.md` data-model description SHALL state that the `sources.enabled` and
`sources.config` columns are reserved for the planned database-backed configuration and are not
unused schema to remove. It SHALL also state what decides which collectors run until that
configuration exists.

#### Scenario: Reserved columns are named

- **WHEN** an agent reads the `sources` entry of the data-model description in `AGENTS.md`
- **THEN** it names `enabled` and `config` as columns reserved for the planned database-backed
  configuration
- **AND** it says they are not to be removed as unused

#### Scenario: Current collector selection is stated

- **WHEN** an agent reads the same entry to learn why a collector does or does not run
- **THEN** it says that, until database-backed configuration exists, the `*_enabled` settings
  read by `build_collectors()` decide which collectors run
