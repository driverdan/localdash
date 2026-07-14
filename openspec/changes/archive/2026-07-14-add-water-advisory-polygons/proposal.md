## Why

Tennessee American Water — the dominant Chattanooga-area water provider — publishes its
Customer Advisory Map from a public, unauthenticated ArcGIS service (the same integration
shape as the existing EPB outage collector). It is the only Chattanooga-area water utility
with machine-readable data; adding it fills an obvious gap on the map. Unlike every current
source, its features are **affected-area polygons**, not points, so landing it well means
teaching the geo stack — which is Point-only today — to carry and draw arbitrary geometry.

## What Changes

- Add a **Tennessee American Water advisory collector** (`tnaw`) that polls the public
  American Water Customer Advisory Map ArcGIS MapServer, filters the national feed to
  Tennessee server-side, and normalizes its three polygon layers (Active–Emergency,
  Active–General, Lifted) into observations keyed by the feed's stable `EventID`. Lifted /
  dropped advisories close via the existing ingest closure sweep. A `docs/` page documents
  the reverse-engineered endpoint, mirroring `docs/epb-outage-api.md`.
- **BREAKING (data model): generalize entity/observation geometry from Point to arbitrary
  geometry.** The `entities.last_geom` and `observations.geom` PostGIS columns move from
  `geometry(Point,4326)` to `geometry(Geometry,4326)` (migration), and the normalization
  contract (`NormalizedObservation`) gains a first-class GeoJSON `geometry` field alongside
  the existing `lat`/`lon` convenience for point sources.
- Rework ingest change-detection and geometry writing to handle non-point geometry (a
  geometry fingerprint replaces `lat`/`lon` movement comparison for polygon sources;
  point sources are unchanged in behavior).
- Serve stored geometry **as-is** in the GeoJSON API responses (entities, track,
  observations) via `ST_AsGeoJSON`, replacing the `ST_X`/`ST_Y` point extraction that
  cannot represent polygons.
- **Draw affected areas on the map as first-class polygons**: the frontend renders polygon
  features as styled/filled areas (colored by advisory type, muted when lifted) in a
  dedicated layer outside the point marker-cluster, with popups, click-to-detail, and
  fly-to by bounds.
- Register the collector and add its config settings (endpoint, state filter, poll
  interval, enable flag), mirroring the EPB settings.

## Capabilities

### New Capabilities
<!-- None. Per project convention, data sources (epb/hc911/tdot) are implementation under
     the `timeseries` capability and documented in docs/, not given their own spec. The
     spec-level change here is the geometry generalization, captured in the modified
     capabilities below. -->

### Modified Capabilities
- `timeseries`: entity and observation geometry is generalized from Point-only to any
  GeoJSON geometry (Point or Polygon); the entities collection, entity track, and
  observations window emit each feature's stored geometry directly, and `bbox` filtering
  intersects against non-point geometry.
- `frontend-timeseries`: the map renders polygon entity features as filled/outlined areas
  distinct from clustered point markers, styled by source/category, with popup, detail
  selection, and viewport focus working for polygon features.

## Impact

- **Code**: new `app/collectors/tnaw.py`, `docs/tnaw-advisory-api.md`; edits to
  `app/collectors/base.py` (geometry field), `app/models.py` + a new Alembic migration
  (column type), `app/ingest.py` (geometry write + change detection), `app/geojson.py`
  (arbitrary-geometry feature), `app/api/timeseries.py` (`ST_AsGeoJSON` serialization,
  bbox), `app/config.py` and `app/collectors/__init__.py` (settings + registration).
- **Frontend**: `MapView.svelte` (polygon layer + rendering), `sources.ts` (advisory
  source config, colors, legend), and the timeseries `types.ts` where geometry is typed.
- **DB migration**: in-place `ALTER COLUMN … TYPE geometry(Geometry,4326)` on
  `entities.last_geom` and `observations.geom`; existing point rows are preserved and GIST
  indexes remain valid.
- **External dependency**: relies on a premium-proxied ArcGIS endpoint
  (`utility.arcgis.com/usrsvcs/...`) that is public today but not a first-party API — mild
  fragility risk, noted in the docs page and handled like other upstreams (source telemetry
  records fetch errors without crashing the scheduler).
