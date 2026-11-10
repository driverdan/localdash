## Why

`NormalizedObservation.status` is a first-class field, but ingest does not store it on the
entity. Ingest stores `obs.properties` as `latest_properties`, and then reads the entity's
previous status back out of `latest_properties["status"]` for change detection
(`app/ingest.py:163`). `GET /entities` does the same when it serves status
(`app/api/timeseries.py:114`). So every collector has an unwritten second duty: copy its status
into `properties["status"]` as well.

EPB (`app/collectors/epb.py:88`) and TN American Water (`app/collectors/tnaw.py:110`) do this by
hand, with comments explaining why. HC911 and TDOT only work because their raw payload happens to
have a `status` key and they pass `properties=item`. A new collector that does not know this
gets a previous status of `None` on every poll. `state_changed()` is then always true, so every
poll writes one observation row and one WebSocket diff per entity. Preventing exactly that is
what ingest is for. The "Adding a data source" section of `AGENTS.md` does not mention the
contract.

## What Changes

- Ingest writes the normalized status into the entity's `latest_properties` itself, on both the
  create and update paths: `latest_properties = {**obs.properties, "status": obs.status}`. The
  normalized `status` always replaces any raw `status` key the payload has. This matches what
  `entity_properties()` already does for REST features and live diffs.
- Change detection keeps reading the previous status from `latest_properties["status"]`. That
  key is now always written by ingest, not by collectors.
- EPB and TNAW stop copying their status into `properties["status"]`, and the comments that
  explain the copy are removed.
- `AGENTS.md` "Adding a data source" states the contract: set `NormalizedObservation.status`;
  ingest does the rest.
- **Observable change (small):** new EPB and TNAW observation rows no longer carry a duplicate
  `status` key inside their JSONB `properties`. The observation's `status` column is unchanged,
  and the track and observations-window endpoints already serve that column as `status`. Older
  rows keep the duplicate key. Entity snapshots, `GET /entities`, and live diffs do not change
  for any current source, because every current source's stored `latest_properties["status"]`
  already equals `obs.status`. No migration or backfill is needed.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `timeseries`: adds a requirement that ingest, not the collector, records the normalized status
  on the entity, and that change detection and the served entity status use it. This covers
  collectors whose `properties` have no `status` key, and raw `status` keys that differ from the
  normalized status.

## Impact

- `app/ingest.py`: the create and update paths in `ingest()` build `latest_properties` from
  `obs.properties` plus the normalized status. `_observation` and `_entity_feature` stay as they
  are (see design.md).
- `app/collectors/epb.py`, `app/collectors/tnaw.py`: remove the manual `status` copy.
- `tests/test_ingest.py`, `tests/test_api_timeseries.py`, `tests/test_epb.py`,
  `tests/test_tnaw.py`: test helpers stop pre-copying status into properties, add tests for the
  new contract, and drop the collector-level assertions on `properties["status"]`.
- `AGENTS.md`: the "Adding a data source" contract note.
- No schema change, no migration, no API shape change, no frontend change.
