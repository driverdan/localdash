## MODIFIED Requirements

### Requirement: Entities collection
The system SHALL serve tracked entities at `GET /api/v1/timeseries/entities` as a GeoJSON FeatureCollection. The collection SHALL support the filters `active` (bool, default `true`), `source` (source key), `category`, `bbox` (`minLon,minLat,maxLon,maxLat`), and `closed_within` (minutes, 0–10080). Each feature's `geometry` SHALL be the entity's stored geometry serialized as-is — a GeoJSON `Point` for point sources or a `Polygon`/`MultiPolygon` for area sources — with no assumption that it is a point. Each feature's properties SHALL merge the entity's latest source properties with the authoritative keys `id`, `source`, `external_id`, `category`, `label`, `last_seen_at`, `active`, and `status` (reported as `Closed` for inactive entities).

#### Scenario: Default returns active entities only
- **WHEN** a client requests `GET /api/v1/timeseries/entities` with no parameters
- **THEN** the response is a GeoJSON FeatureCollection containing only entities with `is_active = true`

#### Scenario: Recently closed entities included via closed_within
- **WHEN** a client requests `GET /api/v1/timeseries/entities?closed_within=60`
- **THEN** the response contains active entities plus inactive entities last seen within the past 60 minutes, and each closed feature carries `active: false` and `status: "Closed"`

#### Scenario: Polygon entity serialized as a polygon feature
- **WHEN** an area source's entity (e.g. a water advisory affected area) is returned
- **THEN** its feature `geometry` is a GeoJSON `Polygon` or `MultiPolygon` reflecting the stored geometry, not a point

#### Scenario: Filtering by source, category, and bbox
- **WHEN** a client passes `source`, `category`, and/or `bbox` parameters
- **THEN** only entities matching every provided filter are returned, with `bbox` evaluated as a PostGIS intersection against the entity's stored geometry (point or polygon)

#### Scenario: Malformed bbox rejected
- **WHEN** a client passes a `bbox` that is not four comma-separated numbers
- **THEN** the API responds `400` with a message describing the expected `minLon,minLat,maxLon,maxLat` format

### Requirement: Entity observation track
The system SHALL serve an entity's full observation history at `GET /api/v1/timeseries/entities/{id}/track`, ordered by `observed_at` ascending, where each item carries `observed_at`, `status`, `geometry` (the observation's stored geometry as GeoJSON, or `null`), `properties`, and — for point observations — the convenience scalars `lon` and `lat` (both `null` for non-point geometry).

#### Scenario: Track for an entity with history
- **WHEN** a client requests the track of an entity that has recorded observations
- **THEN** the observations are returned oldest-first, each with its `geometry`, status, and properties

#### Scenario: Point track exposes lon/lat convenience fields
- **WHEN** a client requests the track of a point-source entity
- **THEN** each item carries `lon` and `lat` populated from its point geometry in addition to `geometry`

#### Scenario: Track for unknown entity
- **WHEN** a client requests the track of an entity id that does not exist
- **THEN** the API responds `404`

### Requirement: Observations window query
The system SHALL serve historical observations at `GET /api/v1/timeseries/observations` as a GeoJSON FeatureCollection, filterable by `source`, `category`, `bbox`, `start`, and `end`, ordered newest-first, with a `limit` defaulting to 5000 and capped at 50000. Each feature's `geometry` SHALL be the observation's stored geometry serialized as-is (point or polygon), and `bbox` SHALL be evaluated as a PostGIS intersection against that geometry.

#### Scenario: Time-window query
- **WHEN** a client requests observations with `start` and `end` timestamps
- **THEN** only observations whose `observed_at` falls within the window are returned, newest first, up to `limit`

#### Scenario: Polygon observation serialized as a polygon feature
- **WHEN** the window contains an area source's observation
- **THEN** its feature `geometry` is the stored `Polygon`/`MultiPolygon`, not a point

#### Scenario: Limit is capped
- **WHEN** a client requests a `limit` greater than 50000
- **THEN** the API rejects the request with a validation error

## ADDED Requirements

### Requirement: Arbitrary entity and observation geometry
The system SHALL store and track each entity's and observation's geometry as an arbitrary PostGIS geometry (`geometry(Geometry,4326)`), supporting at least `Point`, `Polygon`, and `MultiPolygon`, so that area-based sources are first-class. The normalized-observation contract SHALL accept either a point (via `lat`/`lon`) or an explicit GeoJSON `geometry`; when both are absent the entity SHALL have `null` geometry. Change detection SHALL record a new observation when an entity's `status` changes OR its geometry changes, where geometry change is determined by a geometry fingerprint whose point form preserves the prior ~0.1 m movement threshold. Existing point sources SHALL record the same observations they did before this change.

#### Scenario: Polygon source is ingested with polygon geometry
- **WHEN** a collector emits an observation carrying a GeoJSON `Polygon` geometry
- **THEN** the entity and its observation store that polygon, and the API serves it as a polygon feature

#### Scenario: Geometry change records a new observation
- **WHEN** an already-tracked area entity reappears with a materially different affected-area polygon and the same status
- **THEN** a new observation is recorded because the geometry fingerprint changed

#### Scenario: Point-source behavior is unchanged
- **WHEN** a point entity jitters below the movement threshold across polls with unchanged status
- **THEN** no new observation is recorded, matching pre-change behavior
