## MODIFIED Requirements

### Requirement: Arbitrary entity and observation geometry
The system SHALL store and track each entity's and observation's geometry as an arbitrary PostGIS geometry (`geometry(Geometry,4326)`), supporting at least `Point`, `Polygon`, and `MultiPolygon`, so that area-based sources are first-class. The normalized-observation contract SHALL accept either a point (via `lat`/`lon`) or an explicit GeoJSON `geometry`, and SHALL resolve them to a single GeoJSON geometry that ingest uses for storage, change detection, and live diff features: the explicit `geometry` when present, otherwise a GeoJSON `Point` built from `lon`/`lat` when both are present, otherwise `null` geometry. Change detection SHALL record a new observation when an entity's `status` changes OR its geometry changes, where geometry change is determined by a geometry fingerprint of the resolved geometry. The fingerprint of a two-dimensional `Point` SHALL be the string `"<lon>,<lat>"` with each coordinate formatted to 6 decimal places, preserving the prior ~0.1 m movement threshold and the format already stored for point entities; any other geometry SHALL be fingerprinted by a hash of its type and its coordinates rounded to 6 decimal places. Existing point sources SHALL record the same observations they did before this change, and fingerprints stored before a deploy SHALL remain comparable after it.

#### Scenario: Polygon source is ingested with polygon geometry
- **WHEN** a collector emits an observation carrying a GeoJSON `Polygon` geometry
- **THEN** the entity and its observation store that polygon, and the API serves it as a polygon feature

#### Scenario: Geometry change records a new observation
- **WHEN** an already-tracked area entity reappears with a materially different affected-area polygon and the same status
- **THEN** a new observation is recorded because the geometry fingerprint changed

#### Scenario: Point-source behavior is unchanged
- **WHEN** a point entity jitters below the movement threshold across polls with unchanged status
- **THEN** no new observation is recorded, matching pre-change behavior

#### Scenario: Explicit geometry takes precedence over lat/lon
- **WHEN** a collector emits an observation that sets both an explicit GeoJSON `geometry` and `lat`/`lon`
- **THEN** the entity and its observation store the explicit geometry, and the fingerprint and live diff feature are derived from it

#### Scenario: Incomplete point yields null geometry
- **WHEN** a collector emits an observation with no explicit `geometry` and only one of `lat` or `lon`
- **THEN** the entity and its observation have `null` geometry and a `null` fingerprint

#### Scenario: Same point fingerprints identically however it is supplied
- **WHEN** one observation supplies a position as `lat`/`lon` and another supplies the same position as a GeoJSON `Point` `geometry`
- **THEN** both produce the same `"<lon>,<lat>"` fingerprint

#### Scenario: Stored point fingerprints survive a deploy
- **WHEN** an active point entity whose stored fingerprint was written before this change is observed again at the same position with the same status
- **THEN** no new observation is recorded and the entity does not appear in the diff's `updated` list
