## Context

Status passes through the timeseries pipeline in five places:

| Where | Reads status from |
|---|---|
| `ingest()` change detection (`app/ingest.py:163`) | `entity.latest_properties["status"]` (previous) vs `obs.status` (new) |
| `_observation()` (observation row) | `obs.status`, into the `status` column |
| `_entity_feature()` (live diff) | `obs.status`, passed to `entity_properties(status=...)` |
| `GET /entities` (`app/api/timeseries.py:114`) | `latest_properties["status"]` (or `Closed` when inactive) |
| `GET /entities/{id}` and the frontend detail panel | `latest_properties` served raw; `sources.ts` detail rows read `p.status` |

Only the first and last two depend on `latest_properties["status"]`, and nothing in ingest
writes that key. It exists only when the collector puts it in `obs.properties`.

What each current source does, checked against origin/main:

- `hc911`: `status=item.get("status")`, `properties=item`. The key matches by construction.
- `tdot`: `status=item.get("status")`, `properties=item`. The key matches by construction.
- `epb`: `status=item.get("incident_status")`, and copies it by hand as
  `properties={..., "status": item.get("incident_status")}`.
- `tnaw`: `status=EventType or EventStatus`, and copies it by hand as `properties={..., "status": status}`.
  The raw ArcGIS properties have no `status` key of their own.

So for every current source, `latest_properties.get("status") == obs.status` already holds for
every stored entity. No raw payload has a `status` key that differs from the normalized status.

## Goals / Non-Goals

**Goals:**

- A collector meets the status contract by setting `NormalizedObservation.status` and nothing
  else.
- Change detection, `GET /entities`, and the entity detail snapshot all see the normalized
  status, whatever is in the raw payload.
- The contract is written down in `AGENTS.md`.

**Non-Goals:**

- A schema change (a real `Entity.status` column). See the alternative below.
- Changing the observation-row contract (`Observation.status` column) or the WebSocket diff shape.
- Fixing the key order in the observations-window endpoint, where `**props` is spread after the
  `status` column and can override it. With the EPB and TNAW copies removed, no current source
  can trigger it. It is noted under Risks as a possible follow-up, not fixed here.
- Other ingest refactors (geometry representation, injected clock, module location). Those
  belong to the sibling changes listed below.

## Decisions

**1. Ingest writes `status` into `latest_properties`.** Both the create path (`Entity(...)`) and
the update path set `latest_properties = {**obs.properties, "status": obs.status}`, built by one
small private helper (e.g. `_latest_properties(obs)`) so the two paths cannot drift. The
change-detection read at line 163 stays as it is. Its input is now guaranteed, because ingest
wrote it on the previous poll.

*Alternative: a real `Entity.status` column.* This is cleaner in principle: status is a
first-class field and would not hide inside JSONB. It costs more, though:
- a hand-written raw-SQL Alembic migration (the repo's migrations are raw SQL), plus a backfill
  from `latest_properties->>'status'`;
- `GET /entities` and `GET /entities/{id}` change to read the column, and the detail response
  gains a `status` field;
- the frontend detail panel (`DetailPanel.svelte` → `sources.ts` `detail(p, ...)`) reads
  `p.status` from `latest_properties`. It would need to read the new field instead, or the API
  would still have to merge status into `latest_properties`, which gets us back to this design.

The bug is a missing write, not a missing column. Writing the key in ingest fixes it with no
schema, API, or frontend change. A column can still be added later, if status ever needs to be
indexed or queried, without undoing anything here.

**2. The normalized status wins over a raw `status` key.** `"status": obs.status` is spread
after `obs.properties`. This is the same precedence `entity_properties()` already uses for REST
features and live diffs ("our authoritative keys always override"). The table above shows that no
current source is affected. For a future source whose raw payload has an unrelated `status`, the
raw value would be hidden in the snapshot just as it already is in every served feature. Such a
collector should rename that raw key if it needs to keep it. `AGENTS.md` will say so.

**3. A `None` status is written explicitly.** When `obs.status` is `None`, `latest_properties`
gets `"status": None` and does not omit the key. This is equivalent for every reader
(`.get("status")` returns `None` either way, and `state_changed` normalizes falsy to `None`), and
it keeps the rule simple: the key always reflects the last normalized status.

**4. `_observation` and `_entity_feature` are not changed.** Observation rows already store
`obs.status` in their dedicated `status` column, and the track and window endpoints serve that
column. Copying it into the observation JSONB too would only keep a duplicate. `_entity_feature`
already passes `status=obs.status`. After this change, new EPB and TNAW observation rows simply
stop carrying the duplicate `status` key in `properties`, because their collectors no longer
add it. That is the one observable difference (see Risks).

**5. Remove the manual copies in EPB and TNAW.** With ingest owning the key, the copies and their
"ingest dedup and the frontend both read `properties["status"]`" comments are wrong. Keeping them
would suggest to the next collector author that the copy is still needed. EPB keeps `service` and
the raw `incident_status`, and TNAW keeps `advisory_type`. Only the `status` key goes.

**6. Collector-agnostic tests.** The `_obs` / `_poly_obs` helpers in `tests/test_ingest.py` and
`tests/test_api_timeseries.py` currently pre-copy status into `properties`. That hides the bug:
the lifecycle test passes only because the helper does the collector's extra work. The helpers
stop doing this, so the existing lifecycle and API tests exercise the new contract. Dedicated
tests then cover the cases that matter: an unchanged poll with no `status` in properties records
nothing, and a conflicting raw `status` is overridden.

## Risks / Trade-offs

- [New EPB/TNAW observation rows lose `properties.status`] → Nothing reads it. The frontend
  history list uses the track item's top-level `status` (the column). The observations-window
  feature's `status` comes from the column, and with the duplicate gone the column can no longer
  be overridden by a stale props copy. Older rows keep the key, which is harmless.
- [A future raw `status` key that means something else is hidden in `latest_properties`] →
  Same precedence as all served features today. Documented in `AGENTS.md` with a "rename it"
  note.
- [The observations-window endpoint spreads `**props` after its `status` column] → After this
  change no current source puts `status` in observation properties, so it cannot trigger. It
  remains a latent ordering issue for raw-`properties=item` sources whose raw `status` matches
  `obs.status` anyway. Left as a possible follow-up (a natural fit for `add-typed-contracts` or
  `tidy-small-inconsistencies`), not absorbed here.
- [Textual conflicts with sibling changes that edit `app/ingest.py`] → This change is first in
  the suggested landing order and is small (one helper, two call sites), so later siblings rebase
  onto it.

## Migration Plan

No migration or backfill. Every existing entity row already has
`latest_properties["status"] == obs.status`, as shown in Context. The first poll after deploy
rewrites each active entity's `latest_properties` with the same status value, so no spurious
observations or diffs are recorded. Rollback means reverting the commit: the EPB and TNAW copies
return, and stored data needs no change either way.

## Relationship to sibling changes

These are being proposed in parallel from the same architecture review. Suggested landing order:
this change first.

- `unify-observation-geometry` (9) also edits `app/ingest.py`'s create and update paths (the
  geometry and fingerprint fields next to `latest_properties`). Expect a trivial rebase.
  There is no semantic overlap.
- `move-timeseries-into-package` (3) relocates `app/ingest.py` and `app/collectors/`. Landing
  this first means the move carries the new helper. The tasks here use origin/main paths.
- `inject-settings-and-clock` (6) changes how `ingest()` gets `now`. That is the same function,
  but different lines.
- `consolidate-shared-helpers` (7) edits `app/collectors/epb.py` (`_as_float`) near the line
  this change removes. Minor textual proximity only.
- `add-typed-contracts` (8) may type the entity detail response. If it does, the
  `latest_properties` it types will now always contain `status`.

## Open Questions

- Should the follow-up for the observations-window `**props` ordering be filed separately, or
  folded into `add-typed-contracts` when that change defines the observation feature model? This
  proposal leaves it alone either way.
