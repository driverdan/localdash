## Why

`NormalizedObservation` (`app/collectors/base.py`) carries geometry in two forms: `lat`/`lon` for
point sources (hc911, tdot, epb) and `geometry: dict | None` (GeoJSON) for area sources (tnaw).
Every consumer has to resolve "use `geometry`, else build a point from `lat`/`lon`, else none" on
its own. `app/ingest.py` does it three times: `geom_fingerprint`, `_geom_value` and
`_entity_feature`. `app/geojson.py` keeps two feature builders for the same reason: `feature()`
(lon/lat) and `feature_geom()` (GeoJSON). The rule is simple, but it is written out three times,
and a new consumer (or a change to precedence) has to find and update every copy.

## What Changes

- `NormalizedObservation` gains one read-only accessor, `resolved_geometry`, that returns the
  observation's geometry as a GeoJSON geometry dict: `geometry` when set, else a `Point` built
  from `lon`/`lat` when both are set, else `None`. The `lat`/`lon` and `geometry` fields stay as
  they are, so collectors are untouched: `lat`/`lon` remains the convenient way for point sources
  to report a position.
- `app/ingest.py` reads only `obs.resolved_geometry`. `geom_fingerprint`, the SQL geometry value
  and the diff feature each have one path instead of a three-way branch.
- The geometry fingerprint keeps its current stored formats exactly: a 2D `Point` is
  `"lon,lat"` at 6 decimals, and anything else is the sha1 of its coordinate-rounded GeoJSON. The
  point form is now chosen by geometry type rather than by which field the collector filled.
  Fingerprints already stored in `entities.geom_fingerprint` for point entities stay valid, so
  the deploy needs no data migration and point entities do not look "moved".
- Every geometry is written to PostGIS through one expression,
  `ST_SetSRID(ST_GeomFromGeoJSON(...), 4326)`. The point-only EWKT string builder in ingest is
  removed. The stored geometry is the same.
- `app/geojson.py` loses the lon/lat `feature()` helper. `feature_geom()` is the one feature
  builder and is already what the API uses.

Observable behaviour: none for any current source. API responses, WebSocket diffs, stored
geometry and stored fingerprints are byte-for-byte the same for hc911, tdot, epb and tnaw. The one
theoretical difference: a collector that passes a 2D `Point` through `geometry` (none does today;
tnaw's ArcGIS layers are polygon layers) would now get the `"lon,lat"` fingerprint instead of a
sha1. For an entity already stored that way, that means one extra observation on the first poll
after deploy.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `timeseries`: the "Arbitrary entity and observation geometry" requirement now states that the
  observation contract resolves to one canonical GeoJSON geometry (with explicit `geometry` taking
  precedence over `lat`/`lon`), and that the fingerprint's point form applies to any 2D `Point`
  and keeps the existing stored format, so fingerprints survive the change.

## Impact

- `app/collectors/base.py`: add the `resolved_geometry` property and update the field comment.
- `app/ingest.py`: `geom_fingerprint`, `_geom_value` and `_entity_feature` use the accessor; the
  EWKT point builder is removed.
- `app/geojson.py`: remove `feature()`.
- `tests/test_ingest_helpers.py`, `tests/test_geojson.py`, `tests/test_ingest.py`,
  `tests/test_tnaw.py`: test changes listed in `tasks.md`.
- `AGENTS.md`: the "Adding a data source" note on how to report geometry.
- No API shape change, no migration, no new dependencies, no frontend change.
  `GET /entities/{id}/track` keeps its `lon`/`lat` convenience fields. They are derived from the
  stored geometry, which this change does not alter.
