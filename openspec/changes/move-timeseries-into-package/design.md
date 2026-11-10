## Context

The timeseries feature (the `/map` geo pipeline) predates the feature-package convention that
news, events and weather follow. Its code currently lives here:

| Today | Contents | Imported by |
|---|---|---|
| `app/models.py` | `Base` + `Source`, `Entity`, `Observation` | `app/ingest.py`, `app/scheduler.py`, `app/api/timeseries.py`, `app/news/models.py` (`Base`), `app/events/models.py` (`Base`), `alembic/env.py` (`Base`), tests |
| `app/ingest.py` | `ingest()`, `state_changed()`, `geom_fingerprint()` | `app/scheduler.py`, tests |
| `app/schemas.py` | `Diff` only (docstring also promises "API response models") | `app/ingest.py`, tests |
| `app/geojson.py` | `feature`, `feature_geom`, `feature_collection`, `entity_properties` | `app/ingest.py`, `app/api/timeseries.py`, `tests/test_geojson.py` |
| `app/collectors/` | `BaseCollector`, `NormalizedObservation`, the four collectors, `build_collectors()` | `app/scheduler.py`, `app/ingest.py`, tests |

Constraints and findings:

- `app/db.py` calls `get_settings()` and `create_async_engine(...)` at import time. Anything that
  imports it gets an engine, and `alembic/env.py` currently avoids it.
- `alembic/env.py` sets `target_metadata = Base.metadata`. Today that metadata holds the timeseries
  tables only because `Base` and those models share a file. News and events tables are not
  registered there, because env.py never imports those modules. Migrations are hand-written SQL,
  so nothing currently reads `target_metadata`. Open PR #269 would start reading it (see below).
- No test patches any of these modules by dotted string (`monkeypatch.setattr("app.ingest...")`),
  so every reference that has to change is an ordinary `import` statement.
- None of the moved modules creates a logger. The timeseries code logs through
  `localdash.scheduler`, which is a fixed name, so log output does not change.
- Packaging: the Dockerfile's `deps` stage runs `uv sync --locked --no-editable`, which installs a
  real copy of the packages listed in `pyproject.toml` into `/app/.venv`. The runtime stage then
  copies the `app/` source tree to `/app`, and both entry points put `/app` first on `sys.path`:
  `uvicorn app.main:app` adds the working directory, and `alembic.ini` sets `prepend_sys_path = .`.
  So the source tree shadows the installed copy. A package missing from the hand-maintained list
  would therefore not break Docker, local editable installs or CI. It would only leave the
  installed copy incomplete without anyone noticing. Breaking nothing visibly is exactly why the
  hand list is a trap worth removing.

## Goals / Non-Goals

**Goals:**

- All timeseries-only Python code lives under `app/timeseries/`, mirroring `app/news/`,
  `app/events/` and `app/weather/`.
- The declarative `Base` lives in a feature-neutral module that creates no engine, so news and
  events models stop depending on the timeseries models file.
- `Base.metadata` as seen by Alembic holds exactly the tables it holds today.
- A pure move. No change to behaviour, schema, API, WebSocket payloads or log names.
- Docs and specs name the new paths.

**Non-Goals:**

- Moving `run_collector` / `_record_run` out of `app/scheduler.py`. That belongs to
  `unify-refresh-orchestration`, which builds on this package.
- Moving `app/api/timeseries.py`. Routers stay in `app/api/` per the existing convention.
- Registering news and events models in `alembic/env.py`. That belongs to PR #269 (see below).
- Any behavioural or model change: dead columns (`remove-dead-schema`), geometry representation
  (`unify-observation-geometry`), typed response models (`add-typed-contracts`), shared helpers
  (`consolidate-shared-helpers`).

## Decisions

### 1. Package layout

```
app/timeseries/
  __init__.py          docstring only (like app/news/__init__.py); no re-exports
  models.py            Source, Entity, Observation      (from app/models.py, minus Base)
  ingest.py            ingest(), state_changed(), …     (from app/ingest.py)
  diff.py              Diff                             (from app/schemas.py)
  geojson.py           GeoJSON helpers                  (from app/geojson.py)
  collectors/          base.py, hc911.py, tdot.py, epb.py, tnaw.py, __init__.py
app/orm.py             Base
```

Files are moved with `git mv` and otherwise changed only in their import lines and docstrings, so
each moved file stays far above git's 50% rename-similarity threshold. Other branches that edit the
old paths then rebase across the move without trouble (see "Landing order").

`__init__.py` holds a docstring only, with no re-exports. The other feature packages work the same
way, and re-exports would make `import app.timeseries` load the models, the ingest service and
every collector.

### 2. `Base` goes to a new `app/orm.py`

`app/orm.py` contains only the `DeclarativeBase` subclass and a docstring saying that every
feature's models register on it.

*Alternatives considered:*

- **`app/db.py`.** Importing a model would then create the async engine and read settings,
  `alembic/env.py` would build an asyncpg engine it never uses, and any test that imports a model
  would touch the engine. Rejected.
- **Keep `app/models.py` holding only `Base`.** That keeps one top-level module named `models`
  that contains no models. The name invites someone to put a model there again.
- **An `app/db/` package (`base.py` + `session.py`).** Tidier in the long run, but it also rewrites
  every `from app.db import ...` site, and that is outside this change.

### 3. `geojson.py` moves into the timeseries package whole

Its only importers are `app/ingest.py` and `app/api/timeseries.py`. Events locations are served as
plain JSON, not GeoJSON, and news and weather have no geometry. AGENTS.md describes it as "the
convention for all geographic responses", but that is a rule about the response shape. It does
not mean another feature uses the module. `entity_properties()` is explicitly the timeseries
entity contract shared by REST and live diffs.

*Alternatives considered:*

- **Keep `app/geojson.py` shared at the top level.** That leaves a feature-specific function
  (`entity_properties`) in shell space.
- **Split it.** Generic `feature`/`feature_geom`/`feature_collection` would stay in
  `app/geojson.py` and `entity_properties` would move. That splits a 60-line module to serve a
  second geo feature that does not exist.

The AGENTS.md convention line keeps the rule ("all geographic responses are GeoJSON
FeatureCollections") and points at `app/timeseries/geojson.py`. It adds that a second geo feature
should promote the generic helpers to a shared module rather than import timeseries internals.

### 4. `app/schemas.py` becomes `app/timeseries/diff.py`

The module holds one dataclass that describes an ingest result and its bus message. `diff.py` says
what it is, and naming it this way fixes the docstring that promises response models.
`app/timeseries/schemas.py` is deliberately left unused, so `add-typed-contracts` can put
timeseries Pydantic response models there without colliding with `Diff`.
`tests/test_schemas.py` is renamed to `tests/test_diff.py` to match. Other test file names
(`test_ingest.py`, `test_geojson.py`, `test_epb.py`, …) still describe their subjects and stay as
they are, which also keeps the CI workflow comment and AGENTS.md's single-test example valid.

### 5. No compatibility shims

No `app/models.py` or `app/collectors/__init__.py` re-export modules are left behind. Nothing
outside the repo imports these paths, and a shim would let new code keep using the old paths. The
shim would then need its own removal change.

### 6. `alembic/env.py` keeps its metadata identical

env.py changes to:

```python
import app.timeseries.models  # noqa: F401  (registers timeseries tables on Base)
from app.orm import Base
```

This keeps `target_metadata` holding the timeseries tables, as it does today, and nothing more. It
uses the same side-effect-import style that PR #269 uses for news and events, so the two changes
combine by taking both sets of imports (see below).

### 7. `pyproject.toml` uses package discovery

The hand list is replaced with:

```toml
[tool.setuptools.packages.find]
include = ["app", "app.*"]
```

The `include` filter stops discovery from picking up `tests`, `alembic` or anything else at the
repo root. The change only affects what a non-editable install or a built wheel contains. As
described under Context, Docker, CI and editable installs import from the source tree, so the
change cannot alter runtime behaviour. The implementation verifies it by building a wheel and
listing its contents. `uv.lock` records no package list, so it does not change; `uv lock --check`
must still pass. The `[tool.ruff]` section is not touched, which leaves `tighten-python-tooling` a
clean textual merge.

*Alternative:* append `app.timeseries` and `app.timeseries.collectors` to the list and drop
`app.collectors`. That works, but leaves the same trap for the next package.

## Interaction with open PR #269 (`fix-alembic-schema-drift`)

#269, open and untouched since 2026-10-14, adds `alembic check` to CI and aligns models with
migrations. Of the files this change touches, it edits:

- `app/models.py`: index declarations and `spatial_index=False` on `Entity`/`Observation`, plus a
  module-level `Index("ix_obs_source_time", ...)` after `Observation`. These hunks are in the
  model classes, not in `Base`, so they carry over to `app/timeseries/models.py` through rename
  detection. The only adjacent edit is removing `class Base` near the top of the file.
- `app/events/models.py`: an `Index` import and `__table_args__` on `Event`. This change edits only
  the `from app.models import Base` line, about ten lines away, so there should be no conflict.
- `alembic/env.py`: adds `import app.events.models` / `import app.news.models` and an
  `include_object` filter, right next to the `from app.models import Base` line this change
  rewrites. **This hunk conflicts.** The resolution is mechanical: keep #269's two imports, add
  `import app.timeseries.models`, and take `from app.orm import Base`.
- `AGENTS.md`: #269 edits the CI and Migrations sections, which this change does not touch. It was
  written against a pre-`isolate-test-database` AGENTS.md, so it needs a rebase anyway.

#269 also becomes more correct after this move. `alembic check` needs all three features'
tables on `Base.metadata`. Today the timeseries tables get there by accident. After the move every
feature is registered by an explicit import.

**Recommendation:** do not block on #269. If it is revived before this change is implemented,
land it first; its edits are semantic and this change's are mechanical, so redoing the mechanical
side is cheaper. Otherwise land this change and rebase #269 using the resolution above.

## Landing order relative to the sibling refactors

All thirteen sibling proposals are written against the current paths. This change keeps the
suggested slot 3:

- **Before this change.** `ingest-owns-entity-status` (1) edits `app/ingest.py`;
  `add-shared-http-client` (2) edits each collector and adds `app/http.py`. Both are small, and
  their edits carry across the rename.
- **Depends on this change.** `unify-refresh-orchestration` (4) adds the timeseries refresh module
  inside `app/timeseries/` and moves `run_collector` there. It must land after this change.
- **Textual overlap after this change**, resolved by rename detection plus updating import lines:
  `inject-settings-and-clock` (6: collectors and ingest), `consolidate-shared-helpers` (7:
  `hc911._as_float`, `tests/test_hc911_helpers.py`; any helper that only timeseries uses belongs
  in `app/timeseries/`), `add-typed-contracts` (8: `Diff` and typed stats; timeseries response
  models go in `app/timeseries/schemas.py`), `unify-observation-geometry` (9:
  `collectors/base.py`, every collector, `ingest.py`, `geojson.py`, the heaviest overlap),
  `tighten-python-tooling` (11: `noqa` comments in moved files; `pyproject.toml`, but a different
  table), `remove-dead-schema` (12: `Source.config`/`enabled` and relationships in the moved
  `models.py`), and `tidy-small-inconsistencies` (13: possibly moved modules).
- **No overlap.** `decompose-events-upsert` (5: events only) and `extract-spa-serving` (10:
  `main.py` only).

Each later sibling's `tasks.md` names old paths such as `app/ingest.py` and `app/collectors/`.
Whoever applies a sibling after this change lands should read those as their `app/timeseries/`
equivalents. If a sibling is still at the proposal stage when this lands, update its tasks.md
with the openspec-update-change flow. Landing this change early and implementing it quickly is
what keeps the conflict surface small. It is a mechanical change, so it should not sit open while
other implementations pile up behind it.

## Risks / Trade-offs

- [Mapper registration order changes: importing `app.news.models` no longer loads the timeseries
  mappers as a side effect] → No relationship crosses features, and every model module is imported
  through its feature's normal code path before a query runs. To confirm nothing relied on the
  side effect, run `tests/test_news_db.py` and `tests/test_events_ingest.py` on their own, not
  only as part of the full suite. In a full run, other test modules load the timeseries models
  first and would hide the problem.
- [A missed import breaks app start-up rather than a single test] → `tests/test_api_routes.py`
  imports `app.main`, which imports the scheduler and every router. A
  `grep -rnE "app\.(models|ingest|schemas|geojson|collectors)\b"` over `app/`, `tests/` and
  `alembic/` must return nothing. Run `alembic upgrade head` (the test fixture already does this in
  a subprocess) to cover `env.py`.
- [Sibling branches hit rename conflicts] → Minimal content edits in moved files keep rename
  similarity high, and the landing-order notes above apply.
- [Docs links break: `docs/hc911-api.md` links `../app/collectors/hc911.py` and `../app/ingest.py`]
  → Updated in the tasks. A grep for the old paths across `*.md` outside `openspec/` is part of
  verification.

## Migration Plan

No data or deployment migration. The image is rebuilt as usual. Rollback is a plain revert.

## Open Questions

- Is `app/orm.py` the preferred name for the `Base` module? (Alternatives: `app/db_base.py`, or a
  later `app/db/` package.)
- Should `geojson.py` stay shared at the top level instead (decision 3)? The proposal moves it
  because timeseries is its only user.
