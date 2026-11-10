## ADDED Requirements

### Requirement: Ingest owns the entity's latest status
The ingest service SHALL record each observation's normalized `status` (the
`NormalizedObservation.status` field) on its entity itself, whether or not the collector also
copied it into the observation's `properties`. Whenever an entity is created or updated, its
stored `latest_properties` SHALL be the observation's `properties` with a `status` key equal to
the normalized status. That key SHALL replace any raw `status` key in the payload, and it SHALL
be present (as `null`) when the normalized status is absent. Change detection SHALL compare the
new normalized status against this stored status. `GET /api/v1/timeseries/entities` SHALL serve
it as the `status` of an active entity, and `GET /api/v1/timeseries/entities/{id}` SHALL include
it in `latest_properties`. A collector SHALL NOT need to put `status` in `properties` to meet
this contract.

#### Scenario: Unchanged poll without status in properties records nothing
- **WHEN** a collector emits an observation with `status` set and no `status` key in its
  `properties`, and the next poll emits the same entity with the same status and geometry
- **THEN** the second poll records no new observation and the entity appears in neither the
  diff's `new` nor its `updated` list

#### Scenario: Status change without status in properties is detected
- **WHEN** a collector emits an entity with no `status` key in its `properties`, and a later
  poll emits it with a different normalized status
- **THEN** a new observation is recorded and the entity appears in the diff's `updated` list

#### Scenario: Entity serves the normalized status
- **WHEN** an active entity was ingested from an observation whose `properties` have no `status`
  key
- **THEN** its feature in `GET /api/v1/timeseries/entities` carries the normalized `status`, and
  `GET /api/v1/timeseries/entities/{id}` returns `latest_properties` containing that `status`

#### Scenario: Normalized status overrides a raw status key
- **WHEN** a collector emits an observation whose `properties` contain a `status` key different
  from its normalized `status`
- **THEN** the entity's stored `latest_properties["status"]` and its served `status` equal the
  normalized status, and change detection on the next poll compares against the normalized status
