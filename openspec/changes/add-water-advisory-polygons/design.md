## Context

Every current source (hc911, tdot, epb) is a point feed. The geo stack encodes that
assumption end-to-end: `NormalizedObservation` carries only `lat`/`lon`; the PostGIS columns
`entities.last_geom` and `observations.geom` are typed `geometry(Point,4326)`; ingest builds
`POINT(...)` EWKT and detects change by comparing lat/lon movement; the API serializes with
`ST_X`/`ST_Y`; and `MapView.svelte` renders every feature as a clustered Leaflet marker.

Tennessee American Water's Customer Advisory Map (verified live during exploration) is a
public, unauthenticated ArcGIS MapServer whose features are **affected-area polygons**:

```
awgis.amwater.com/CustomerAdvisoryMap/   (Esri Web AppBuilder)
  └─ webmap 3791d39fd2384eb7947769093b9dc53b (org AMWater, public)
       └─ utility.arcgis.com/usrsvcs/servers/482bbe.../CustomerAdvisoryMap/DisplayData_SDE/MapServer
            ├─ 17 Active Advisory – Emergency  (polygon)
            ├─ 16 Active Advisory – General    (polygon)
            └─ 15 Lifted Advisory              (polygon)
```

The feed is national — it must be filtered to `EventState='TN'` server-side — and low-volume
(a handful of TN advisories at a time). Each record has a **stable `EventID`**, rich fields
(`EventNotificationType`, `EventType`, `EventStatus`, start/completion/expiration dates,
`EventHeader`, `EventMessage`, `EventHyperlink`), and polygon geometry. Like every source it
is a snapshot, so LocalDash builds the time-series by polling, and the existing closure sweep
retires advisories that drop out of the feed.

## Goals / Non-Goals

**Goals:**
- Ingest TN American Water advisories via a collector that mirrors the `epb` integration shape
  (docs page + `BaseCollector` subclass + config settings + registry entry).
- Generalize the geo pipeline so an entity/observation geometry can be a Point **or** a Polygon
  (or MultiPolygon), source-agnostically — no per-source columns or tables.
- Draw advisory affected-areas on the map as first-class filled polygons, styled by advisory
  type, with popup, click-to-detail, and viewport focus.
- Leave all existing point sources behaviorally unchanged (same rows recorded, same rendering).

**Non-Goals:**
- Ingesting the **Lifted Advisory** layer (15) as its own entities — a lifted advisory is one
  that left the Active layers, so the existing closure sweep already retires it. Layer 15 stays
  a documented-but-unused fallback.
- Onboarding the smaller Chattanooga water districts (Hixson, Eastside, Walden's Ridge) — they
  publish only text alert pages with no machine-readable geo data.
- Polygon editing, area/statistics computation, or a general legend overhaul.
- Any change to the WebSocket diff envelope shape (it already carries GeoJSON features, which
  now simply contain polygon geometry).

## Decisions

### 1. One generic geometry column, not a second polygon column
Change `entities.last_geom` and `observations.geom` from `geometry(Point,4326)` to
`geometry(Geometry,4326)` in place. A single generic-geometry column keeps every query
(`ST_Intersects` bbox, GIST index, `ST_AsGeoJSON`) source-agnostic and uniform.
*Alternatives:* a parallel `last_geom_poly` column (rejected — bifurcates every read and the
bbox filter); a per-source polygon table (rejected — breaks the "new source = no schema change"
ethos). Existing point rows remain valid `geometry` values; only the type constraint widens.

### 2. `NormalizedObservation` gains a first-class `geometry`, keeps `lat`/`lon`
Add an optional `geometry: dict | None` (a GeoJSON geometry) to `NormalizedObservation`.
Point collectors keep setting `lat`/`lon` and are untouched; polygon collectors set `geometry`.
Ingest resolves the write geometry as: use `geometry` when present (→
`ST_SetSRID(ST_GeomFromGeoJSON(:g), 4326)`), else fall back to the existing
`SRID=4326;POINT(lon lat)` EWKT path.
*Alternative:* replace `lat`/`lon` with a single `geometry` everywhere (rejected — needless
churn across three working collectors and their tests).

### 3. Unified change-detection via a geometry fingerprint
`state_changed` today records a new observation when status changes or the point moved
(`POSITION_EPS ≈ 0.1 m`). Replace the movement test with a **geometry fingerprint** compared
prev-vs-new:
- point geometry → `f"{lon:.6f},{lat:.6f}"` (6 decimals ≈ the current 0.1 m threshold, so point
  behavior is preserved),
- polygon/other → a hash of the geometry coordinates rounded to 6 decimals.

Store the fingerprint on the entity (new nullable `geom_fingerprint` column) so the ingest load
can compare it without `ST_X`/`ST_Y` (which return NULL for polygons). A new observation is
recorded when **status changed OR the fingerprint changed** — subsuming the old movement rule.
*Alternative:* trust the feed's `EventLastUpdatedDate` (rejected — source-specific; the
fingerprint keeps ingest generic and also fixes the "closed then reappears" and polygon-redraw
cases for any future source).

### 4. Serialize stored geometry as-is with `ST_AsGeoJSON`
Replace `ST_X`/`ST_Y` selection in `/entities`, `/entities/{id}/track`, and `/observations`
with `ST_AsGeoJSON(geom)`, and add `geojson.feature_geom(geometry, properties, fid)` that embeds
a parsed GeoJSON geometry object directly. Point features still emit `{"type":"Point",...}`, so
existing clients are unaffected; polygon features now emit `{"type":"Polygon",...}`. Track items
gain a `geometry` field; `lon`/`lat` stay populated for point geometries for back-compat.
The `bbox` filter is already `ST_Intersects(column, envelope)` and works unchanged on polygons.

### 5. Frontend: a dedicated polygon layer beside the marker cluster
`MapView.svelte` branches on `f.geometry.type`:
- **Point** → the existing `divIcon` glyph marker into the `markerClusterGroup` (unchanged).
- **Polygon/MultiPolygon** → an `L.geoJSON` layer in a **separate, non-clustered** `LayerGroup`
  (clustering only makes sense for point markers), styled by `sources.ts`: fill/stroke colored
  by advisory category (emergency vs general), muted when closed/lifted, with the same popup and
  `click → ts.detailId` wiring. Table "fly to" and any centroid needs use the polygon's Leaflet
  `getBounds()` (fit) rather than a lat/lon point.

`sources.ts` gets a `tnaw` config (short name, title/location/jurisdiction accessors from
`EventHeader`/`EventType`/`EventMessage`, category colors, icon) plus a fallback so unknown
geometry/sources still render. The advisory categories are `emergency` and `general`; the
detail-panel observation "track" list still renders (status history), while the on-map dashed
track (circle markers + polyline) is guarded to point geometry and is simply a no-op for
polygon entities.

### 6. Collector shape (`tnaw`)
`fetch()` GETs the two Active layers (16, 17) with
`where=EventState='TN'&outFields=*&returnGeometry=true&outSR=4326&f=geojson`; `normalize()` maps
each GeoJSON feature to a `NormalizedObservation` with `external_id = str(EventID)`,
`category = emergency|general` (from `EventNotificationType`/layer), `label = EventHeader`,
`status = EventStatus`/`EventType`, `geometry =` the feature geometry, and `properties =` the
flattened attributes plus `EventHyperlink`. Config settings mirror `epb_*`:
`tnaw_api_base_url`, `tnaw_state` (default `TN`), `tnaw_layers`, `tnaw_poll_interval`,
`tnaw_enabled`. Registered in `build_collectors()`.

## Risks / Trade-offs

- **Premium-proxied, non-first-party endpoint** (`utility.arcgis.com/usrsvcs/...`) → it is public
  today but could change or start requiring a token. *Mitigation:* treat like any upstream —
  errors are captured into source telemetry (`last_status`/`last_error`) without crashing the
  scheduler; the docs page records the full reverse-engineering trail so it can be re-derived.
- **Column type change on live tables** → widening `Point`→`Geometry` and adding a column.
  *Mitigation:* migration uses `ALTER COLUMN … TYPE geometry(Geometry,4326) USING …`, and
  drops/recreates the GIST indexes to avoid typmod-tied index staleness. Existing point rows are
  preserved (a Point is a valid generic geometry). Down-migration narrows back to `Point` (valid
  only while no polygon rows exist — acceptable for a dev-stage rollback).
- **MultiPolygon advisories** → some affected areas may be MultiPolygon. *Mitigation:* the
  generic column and `ST_GeomFromGeoJSON`/`L.geoJSON` handle both; no special-casing.
- **National feed / accidental broad ingest** → forgetting the `EventState` filter would pull
  hundreds of out-of-region advisories. *Mitigation:* the filter is applied server-side in the
  query `where` clause and defaulted in config; the docs page calls it out.
- **Fingerprint vs point parity** → rounding at 6 decimals must reproduce the old 0.1 m movement
  threshold. *Mitigation:* covered by a unit test asserting point sources record the same
  observations as before across a sub-threshold jitter and an above-threshold move.

## Migration Plan

1. Alembic migration: drop GIST indexes on `entities.last_geom` / `observations.geom`; `ALTER
   COLUMN … TYPE geometry(Geometry,4326)`; recreate the GIST indexes; add nullable
   `entities.geom_fingerprint text`. Backfill `geom_fingerprint` for existing point entities
   (optional — NULL simply forces one extra observation on next poll).
2. Ship the geometry-generalized ingest/serialization + the `tnaw` collector (disabled-by-config
   default off is unnecessary; enable it like epb).
3. `docker compose up --build` runs the migration on startup, then serves.
4. **Rollback:** revert the code; the down-migration narrows the column back to `Point` and drops
   `geom_fingerprint` (safe while no polygon rows exist). If polygon rows exist, disable `tnaw`
   and leave the generic column — reads still work.

## Open Questions

- Should `status` be `EventStatus` (mostly constant "Active") or `EventType` (Planned Work /
  Emergency Repair, more informative on the map)? Leaning `EventType`; resolve during impl.
- Do we want the detail panel to show the affected-area on its own (fit-to-bounds) when opened,
  beyond the existing status list? Low cost, deferrable.
