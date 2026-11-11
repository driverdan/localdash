## 1. Canonical geometry on the observation model

- [x] 1.1 In `app/collectors/base.py`, add a read-only `@property resolved_geometry -> dict[str, Any] | None` to `NormalizedObservation`: return `geometry` when set, else `{"type": "Point", "coordinates": [lon, lat]}` when both `lat` and `lon` are set, else `None`. Use a plain property, not a Pydantic `computed_field`, so `model_dump()` is unchanged
- [x] 1.2 Update the field comment above `geometry` to say point sources set `lat`/`lon`, area sources set `geometry`, explicit `geometry` wins, and consumers read `resolved_geometry` rather than the raw fields

## 2. Single geometry path in ingest

- [x] 2.1 Rewrite `geom_fingerprint` in `app/ingest.py` over `obs.resolved_geometry`: `None` → `None`; a `Point` with exactly two coordinates → `f"{float(lon):.6f},{float(lat):.6f}"` (the format already stored); otherwise the existing sha1 of `{"type", "coordinates": _round_coords(...)}`. Update the docstring to say the point form is kept byte-identical so stored fingerprints stay valid
- [x] 2.2 Rewrite `_geom_value` to return `None` when `obs.resolved_geometry` is `None`, else `func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(g)), 4326)`. Remove the EWKT point string and the "fast path" wording
- [x] 2.3 In `_entity_feature`, replace the `geometry`/`lat`-`lon` branch with `feature_geom(obs.resolved_geometry, props, fid=entity.id)`, and drop `feature` from the `app.geojson` import
- [x] 2.4 Confirm with `grep` that nothing in `app/` other than `NormalizedObservation.resolved_geometry` reads `obs.lat`, `obs.lon` or `obs.geometry` to decide geometry. Collectors that set these fields are expected matches

## 3. GeoJSON helpers

- [x] 3.1 Delete `feature()` from `app/geojson.py` once grep shows no remaining callers in `app/`. Keep `feature_geom()` under its current name

## 4. Tests

- [x] 4.1 `tests/test_ingest_helpers.py`: keep the existing assertions as written, including `geom_fingerprint(_obs(lat=35.04, lon=-85.31)) == "-85.310000,35.040000"`, the partial lat/lon → `None` cases, jitter and move, and the polygon cases. They pin the stored format
- [x] 4.2 `tests/test_ingest_helpers.py`: add a test that a GeoJSON `Point` supplied via `geometry` fingerprints identically to the same position supplied as `lat`/`lon`, and one that a 3D `Point` (`[lon, lat, z]`) uses the hashed form and changes when `z` changes
- [x] 4.3 `tests/test_ingest_helpers.py` (or a new `tests/test_collectors_base.py` if that reads better): unit tests for `resolved_geometry`: lat/lon → Point with `[lon, lat]` order; explicit `geometry` wins when lat/lon are also set; only one of lat/lon → `None`; nothing set → `None`; `model_dump()` has no `resolved_geometry` key
- [x] 4.4 `tests/test_geojson.py`: remove `test_feature_with_point_geometry`, `test_feature_without_coordinates_has_null_geometry` and `test_feature_missing_one_coordinate_is_null_geometry`, and rewrite `test_feature_collection_wraps_features` to build its feature with `feature_geom`. The null-geometry behaviour is covered by 4.3 and the existing `test_feature_geom_allows_null_geometry`
- [x] 4.5 `tests/test_ingest.py` (DB): add a test that ingesting a lat/lon observation stores a point whose `ST_AsText(last_geom)` and observation `ST_AsText(geom)` equal `POINT(<lon> <lat>)`, with `geom_fingerprint` equal to the `"lon,lat"` 6-decimal string
- [x] 4.6 `tests/test_ingest.py` (DB): add a deploy-continuity test that seeds an active entity directly with `geom_fingerprint="-85.310000,35.040000"`, status `Queued` in `latest_properties`, and a matching point `last_geom`, then ingests the same position and status. Assert no new observation row and an empty `diff.updated`
- [x] 4.7 `tests/test_ingest.py`: confirm `test_ingest_polygon_geometry`, `test_ingest_full_lifecycle` and `test_diff_features_share_rest_property_contract` pass unchanged (point and polygon diff features keep the same shape)
- [x] 4.8 `tests/test_tnaw.py`: add an assertion that a normalized advisory's `resolved_geometry` is the feature's polygon geometry, unchanged

## 5. Docs

- [x] 5.1 `AGENTS.md`, "Adding a data source": add one sentence saying point sources set `lat`/`lon`, area sources set a GeoJSON `geometry` (which wins if both are set), and ingest reads only `NormalizedObservation.resolved_geometry`
- [x] 5.2 `AGENTS.md`, the ingest bullet "append an `observation` only when state changed": note that the point fingerprint format (`lon,lat` at 6 decimals) is persisted in `entities.geom_fingerprint` and must not change without a data migration, or every point entity records a spurious observation on the next poll

## 6. Verify

- [x] 6.1 Run the backend test suite and the ruff lint/format checks; all pass
- [x] 6.2 Rebuild and restart via Docker (`sg docker -c 'docker compose up --build -d'`). After two poll cycles, confirm that the first poll after deploy did not add one observation per active point entity: compare `observations` row counts per source for the poll before and after, or check that the first WebSocket diff's `updated` list is no larger than usual
- [x] 6.3 Spot-check `GET /api/v1/timeseries/entities/{id}/track` for a point entity and a tnaw entity. The point items still carry `lon`/`lat`. The tnaw items still carry polygon `geometry` with `lon`/`lat` null
