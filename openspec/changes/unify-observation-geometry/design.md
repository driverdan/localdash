## Context

The archived `add-water-advisory-polygons` change (decision 2) added `geometry: dict | None` to
`NormalizedObservation` beside the existing `lat`/`lon`. It rejected replacing `lat`/`lon` outright
as "needless churn across three working collectors and their tests". That reasoning still holds.
The cost it left behind is that every consumer of an observation re-derives its geometry:

- `geom_fingerprint` (`app/ingest.py:62-78`): `geometry` → sha1 of coordinate-rounded GeoJSON;
  else `lat`/`lon` → `f"{lon:.6f},{lat:.6f}"`; else `None`.
- `_geom_value` (`app/ingest.py:81-91`): `geometry` →
  `ST_SetSRID(ST_GeomFromGeoJSON(json), 4326)`; else `lat`/`lon` → EWKT string
  `SRID=4326;POINT(lon lat)` (GeoAlchemy2 wraps it); else `None`.
- `_entity_feature` (`app/ingest.py:107-109`): `geometry` → `feature_geom()`; else
  `feature(lon, lat)`, which itself returns a null geometry unless both are set.

`app/geojson.py` has `feature()` only to serve that last branch. The API (`app/api/timeseries.py`)
already uses `feature_geom()` exclusively, because it reads geometry back from PostGIS as GeoJSON.

Current sources: hc911, tdot and epb set `lat`/`lon`. tnaw sets `geometry` from ArcGIS polygon
layers (16, 17), so in practice it supplies `Polygon`/`MultiPolygon` and never a `Point`.

`entities.geom_fingerprint` persists the fingerprint between polls. `state_changed` compares the
stored value with the new one, so any change to the format makes every affected entity look moved
once.

## Goals / Non-Goals

**Goals:**

- One place decides what an observation's geometry is. Ingest has a single geometry path.
- Stored fingerprints, stored geometry, API output and WebSocket diffs are unchanged for every
  current source, so the deploy causes no spurious observations.
- Collectors keep their current, ergonomic inputs.

**Non-Goals:**

- Removing `lat`/`lon` from `NormalizedObservation` or changing any collector.
- Changing the API's track `lon`/`lat` convenience fields (`app/api/timeseries.py:166-170`). They
  are derived from stored geometry and this change does not touch them.
- Validating GeoJSON geometry (type/coordinate shape) beyond what PostGIS already rejects.
- Deduplicating the events EWKT builder (`app/events/ingest.py:38`). That belongs to
  `consolidate-shared-helpers`.

## Decisions

### 1. A read-only `resolved_geometry` property on `NormalizedObservation`

```python
@property
def resolved_geometry(self) -> dict[str, Any] | None:
    if self.geometry is not None:
        return self.geometry
    if self.lat is not None and self.lon is not None:
        return {"type": "Point", "coordinates": [self.lon, self.lat]}
    return None
```

The precedence matches today's behaviour exactly: explicit `geometry` wins, both `lat` and `lon`
are needed for a point, and anything else is null geometry. It is a plain `@property`, not a
Pydantic `computed_field`, so `model_dump()` output and the validated fields stay as they are.

*Alternatives:*
- A `model_validator` that folds `lat`/`lon` into `geometry` at construction. Rejected: `geometry`
  would then mean "explicit input" before validation and "resolved value" after, and a reader of
  `obs.geometry` could not tell which form the collector used. A derived property keeps inputs and
  the derived value separate.
- Replace `lat`/`lon` with `geometry` in every collector. Rejected for the same reason as in
  `add-water-advisory-polygons`. Point collectors would each build the same dict, and their
  normalize tests would churn for no behavioural gain.
- Reject observations that set both `geometry` and `lat`/`lon`. No collector does this today.
  Rejecting it would be a new validation rule that could fail a poll, so it is out of scope (see
  Open Questions).

### 2. Fingerprint by geometry type, keeping the stored formats exactly

`geom_fingerprint(obs)` takes `g = obs.resolved_geometry`:

- `g is None` → `None`.
- `g["type"] == "Point"` with exactly two coordinates → `f"{float(lon):.6f},{float(lat):.6f}"`.
- anything else → sha1 of `{"type", "coordinates": rounded}` as today.

For every lat/lon source the input floats are the same and the format string is the same, so the
fingerprint is byte-identical to what is stored. For tnaw polygons the sha1 input is unchanged.
**No data migration is needed and no entity looks moved after deploy.**

The only input whose fingerprint changes is a 2D `Point` supplied through `geometry`. Today that
gets a sha1; after this change it gets `"lon,lat"`. No current source produces one. If a future or
existing entity did, it would record one extra observation and one diff on the first poll after
deploy, then be stable. A 3D point (`[lon, lat, z]`) keeps the sha1 form, so elevation is still
part of change detection.

*Alternatives considered for the hazard:*
- Change the point format (for example, hash everything uniformly) and accept the blip. Rejected:
  every active hc911/tdot/epb entity would record a duplicate observation and appear as "updated"
  in one large diff after deploy. That is pure noise in the time-series, and avoiding it costs
  nothing.
- Change the format and recompute `entities.geom_fingerprint` in a hand-written SQL migration.
  Rejected: the fingerprint is computed in Python (`:.6f` formatting, sha1 over a JSON
  serialisation with Python's float repr). Reproducing that in SQL is fragile, and getting it
  slightly wrong is the same blip with extra work.
- Branch on which field the collector set (keep sha1 for `geometry` points). Rejected: that keeps
  the origin-based branch this change exists to remove, and two representations of the same point
  would fingerprint differently.

### 3. One SQL geometry expression for all geometry

`_geom_value(obs)` becomes `None` when there is no geometry, otherwise
`func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(g)), 4326)`. The EWKT point string goes away.

The stored value is the same. `json.dumps` and the current f-string both render a Python float with
its shortest round-trip `repr`, so PostGIS parses identical doubles and stores the same 2D
`POINT` with SRID 4326. The closure sweep copies `entity.last_geom`, the API reads geometry with
`ST_AsGeoJSON`, and the track endpoint derives `lon`/`lat` from that, so none of them can see a
difference. The polygon path has used this expression since migration `0006`, so the
entity-plus-observation write with a SQL expression is already exercised.

The code comment calls the EWKT path the "fast path". The difference is a `json.dumps` per row and
a server-side GeoJSON parse instead of EWKT parse, for at most a few hundred point rows per poll
across all sources. That is not measurable against the network fetch. A single path is worth more
here than a micro-optimisation nobody has measured.

*Alternative:* keep EWKT for `Point` and GeoJSON for everything else, branching on
`g["type"]`. This is acceptable if the reviewer prefers it: it still has a single input (the
resolved geometry), so the origin branch is still gone. It was not chosen because it keeps two SQL
forms of the same geometry and a second EWKT builder for `consolidate-shared-helpers` to share.

### 4. `_entity_feature` uses `feature_geom`; `feature()` is removed

`_entity_feature` calls `feature_geom(obs.resolved_geometry, props, fid=entity.id)`. Once that
call is gone, nothing in `app/` calls `geojson.feature()`. It is deleted, along with its tests
(their null-geometry cases move to the `resolved_geometry` tests). `feature_geom` keeps its name.
Renaming it to `feature` would touch the API module and its imports for no behavioural gain, and
would collide with sibling changes editing those imports.

## Relationship to sibling changes

These are proposed in parallel. Suggested landing order: `ingest-owns-entity-status`,
`add-shared-http-client`, `extract-orm-base`, `unify-refresh-orchestration`,
`decompose-events-upsert`, `inject-settings-and-clock`, `consolidate-shared-helpers`,
`add-typed-contracts`, this change, `extract-spa-serving`, `tighten-python-tooling`,
`remove-dead-schema`, `tidy-small-inconsistencies`.

- **`ingest-owns-entity-status`** edits `ingest()` and `_entity_feature` in the same file. This
  change touches only the geometry line of `_entity_feature`, so whichever lands second rebases
  trivially. No semantic overlap.
- **`extract-orm-base`** (formerly `move-timeseries-into-package`) no longer moves any files:
  `app/ingest.py`, `app/collectors/` and `app/geojson.py` stay where they are, so the paths in the
  tasks hold and there is no overlap.
- **`consolidate-shared-helpers`** dedupes the EWKT point builders at `app/ingest.py:90` and
  `app/events/ingest.py:38`. This change deletes the ingest copy. If consolidation lands first,
  this change removes timeseries ingest's call to the shared helper, and events remains its only
  caller. If this change lands first, consolidation has one builder left and nothing to dedupe on
  that item. Either order works. The second to land should check the other's result.
- **`add-typed-contracts`** adds Pydantic response models. The track response keeps its
  `lon`/`lat` fields and this change alters no response shape, so there is no conflict.
- **`tighten-python-tooling`** adds a type checker. `resolved_geometry` is annotated
  `dict[str, Any] | None` so it fits whatever checker is chosen.

## Risks / Trade-offs

- **[Risk] A collector (now or later) passes a 2D Point via `geometry`.** → Its fingerprint format
  changes once, so it records one extra observation after deploy. No current source does this.
  This is called out as the change's one observable difference.
- **[Risk] The GeoJSON SQL path stores a point slightly differently from EWKT.** → Both are parsed
  from the same float repr. A DB test asserts the stored point text (`ST_AsText`) and the track
  `lon`/`lat` for a lat/lon source are unchanged.
- **[Risk] Fingerprint continuity is assumed, not checked.** → A DB test seeds an entity with
  today's stored fingerprint string, re-ingests the same position and status, and asserts no new
  observation and an empty `updated` diff.
- **[Trade-off] `geometry` and `lat`/`lon` both remain on the model.** → Collectors still have two
  inputs. The goal is one *read* path, not one input field, and the property's docstring and the
  field comment state the precedence.

## Migration Plan

None. No schema or data change. Deploy is a normal rebuild. Rollback is a code revert, and the
fingerprints written in between use the same format either way.

## Open Questions

- Should `NormalizedObservation` reject an observation that sets both `geometry` and
  `lat`/`lon`? Today `geometry` silently wins. This proposal keeps that behaviour. A validator
  would be stricter but could turn a collector bug into a failed poll.
