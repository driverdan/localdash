## ADDED Requirements

### Requirement: Timeseries diff features share the entity property contract
Every feature in a timeseries diff's `new` and `updated` arrays SHALL carry the same property
contract as a feature from `GET /api/v1/timeseries/entities`. Its properties SHALL be the entity's
latest source properties, overridden by the authoritative keys `id`, `source`, `external_id`,
`category`, `label`, `last_seen_at`, `active`, and `status`. Raw source properties SHALL NOT
override an authoritative key. The diff and REST features SHALL be built by one shared helper so
the two shapes cannot drift.

#### Scenario: Diff feature carries last_seen_at and active
- **WHEN** a poll cycle creates or updates an entity
- **THEN** the diff feature's properties include `last_seen_at` (the cycle's ingest time) and
  `active: true`, matching what `GET /entities` would return for that entity

#### Scenario: Raw upstream id does not clobber the entity id
- **WHEN** a source's raw item carries its own `id` property (e.g. an upstream incident id)
- **THEN** the diff feature's `properties.id` is the LocalDash entity id, as it is in the REST
  feature
