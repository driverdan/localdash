## 1. Geometry generalization — data model & migration

- [ ] 1.1 Change `entities.last_geom` and `observations.geom` in `app/models.py` from `Geometry("POINT", ...)` to `Geometry("GEOMETRY", srid=4326, spatial_index=True)`; add nullable `geom_fingerprint` text column to `Entity`.
- [ ] 1.2 Write a hand-written Alembic migration: drop the GIST indexes on `entities.last_geom` / `observations.geom`, `ALTER COLUMN … TYPE geometry(Geometry,4326) USING …`, recreate the GIST indexes, and add `entities.geom_fingerprint text` (nullable). Provide a down-migration that narrows back to `Point` and drops the column.
- [ ] 1.3 Verify the migration runs clean on an existing DB (`docker compose up --build`) with current point rows preserved.

## 2. Normalization & ingest

- [ ] 2.1 Add optional `geometry: dict | None` (GeoJSON geometry) to `NormalizedObservation` in `app/collectors/base.py`; document that point collectors keep using `lat`/`lon`.
- [ ] 2.2 In `app/ingest.py`, resolve the write geometry: `ST_SetSRID(ST_GeomFromGeoJSON(:g), 4326)` when `geometry` is set, else the existing `SRID=4326;POINT(lon lat)` EWKT path.
- [ ] 2.3 Add a `geom_fingerprint()` helper (point → `f"{lon:.6f},{lat:.6f}"`; polygon/other → hash of coords rounded to 6 decimals) and store it on the entity at upsert.
- [ ] 2.4 Rework `state_changed()` to record a new observation when status changed OR fingerprint changed; drop the `ST_X`/`ST_Y`-based movement comparison from the entity-load query in favor of reading `geom_fingerprint`.
- [ ] 2.5 Update the closure-sweep observation and `_entity_feature`/`feature` calls to carry geometry (not just lon/lat).

## 3. GeoJSON serialization & API

- [ ] 3.1 Add `feature_geom(geometry: dict, properties, fid)` to `app/geojson.py` that embeds a parsed GeoJSON geometry directly.
- [ ] 3.2 In `app/api/timeseries.py` `/entities`, select `ST_AsGeoJSON(Entity.last_geom)` instead of `ST_X`/`ST_Y` and emit each feature via `feature_geom`.
- [ ] 3.3 Update `/observations` the same way (`ST_AsGeoJSON(Observation.geom)` → `feature_geom`).
- [ ] 3.4 Update `/entities/{id}/track` to return `geometry` per item (parsed `ST_AsGeoJSON`), keeping `lon`/`lat` populated only for point geometry.
- [ ] 3.5 Confirm the `bbox` filter (`ST_Intersects`) works unchanged against polygon geometry.

## 4. Tennessee American Water collector (`tnaw`)

- [ ] 4.1 Write `docs/tnaw-advisory-api.md` documenting the reverse-engineered endpoint (Web AppBuilder → webmap `3791d39fd2384eb7947769093b9dc53b` → MapServer), the three layers, the `EventState='TN'` filter, the field reference, `f=geojson`, and the premium-proxy fragility caveat — mirroring `docs/epb-outage-api.md`.
- [ ] 4.2 Add `tnaw_*` settings to `app/config.py` (`tnaw_api_base_url`, `tnaw_state="TN"`, `tnaw_layers` for the two Active layers, `tnaw_poll_interval`, `tnaw_enabled`) and to `.env.example`.
- [ ] 4.3 Implement `app/collectors/tnaw.py` (`TnawCollector`): `fetch()` GETs Active-Emergency (17) and Active-General (16) with `where=EventState='TN'&outFields=*&returnGeometry=true&outSR=4326&f=geojson`; `normalize()` maps each GeoJSON feature to a `NormalizedObservation` keyed by `EventID`, with `category` = `emergency`/`general`, `label` = `EventHeader`, `status` = `EventType`, `geometry` = the feature geometry, and `properties` = flattened attributes incl. `EventHyperlink`.
- [ ] 4.4 Register `TnawCollector` in `app/collectors/__init__.py` behind `settings.tnaw_enabled`.
- [ ] 4.5 Manually trigger `POST /api/v1/timeseries/sources/tnaw/refresh` and confirm TN advisories (incl. a Chattanooga one) are ingested with polygon geometry.

## 5. Frontend — polygon rendering

- [ ] 5.1 Add a `tnaw` config to `features/timeseries/sources.ts` (short name, title/location/jurisdiction accessors from advisory fields, `emergency`/`general` category colors, icon) and ensure the fallback config covers polygon features.
- [ ] 5.2 Type the geometry union in `features/timeseries/types.ts` so `TrackedFeature.geometry` may be Point or Polygon/MultiPolygon.
- [ ] 5.3 In `MapView.svelte`, add a dedicated non-clustered `LayerGroup` for polygons; branch the render `$effect` on `geometry.type` — points to the cluster (unchanged), polygons via `L.geoJSON` styled by category, muted when closed, with popup + `click → ts.detailId`.
- [ ] 5.4 Reconcile polygon layers against the visible set the same way markers are (add/remove/replace by feature identity), so live diffs update polygons incrementally.
- [ ] 5.5 Make table "fly to" / focus fit polygon bounds (`getBounds()`) for polygon entities while keeping `flyTo` for points; guard the detail-track circle/polyline drawing to point geometry (no-op for polygons).

## 6. Tests & verification

- [ ] 6.1 Unit-test `geom_fingerprint()` / `state_changed()`: point jitter below threshold records nothing, above-threshold move records, and a polygon reshape records (point-source parity preserved).
- [ ] 6.2 Unit-test `TnawCollector.normalize()` against a captured TN GeoJSON fixture (stable `EventID` key, category split, geometry passthrough).
- [ ] 6.3 API test: an entity/observation with polygon geometry round-trips through `/entities`, `/observations`, and `/entities/{id}/track` as a polygon feature, and `bbox` intersects it.
- [ ] 6.4 Run the full stack (`docker compose up --build`), load `/map`, and confirm TN advisory polygons draw, are styled by type, pop up, open detail, and fit-to-bounds from the table; confirm existing point sources are unchanged.
