## Why

News, events and weather each live in their own package (`app/news/`, `app/events/`,
`app/weather/`), but timeseries, the original feature, is spread across five top-level locations:
`app/ingest.py`, `app/models.py`, `app/schemas.py`, `app/geojson.py` and `app/collectors/`. Two
problems follow from this:

- **`Base` is defined in the timeseries models file.** `app/models.py` holds both the shared
  SQLAlchemy `DeclarativeBase` and the timeseries tables (`Source`/`Entity`/`Observation`). So
  `app/news/models.py:26`, `app/events/models.py:30` and `alembic/env.py:13` all import `Base` from
  `app.models`, and importing either sibling feature's models also loads the timeseries mappers.
- **The top level mixes shell and feature code.** You can't tell from `app/` which modules are
  app-shell (`config`, `db`, `ws`, `scheduler`, `redaction`, `main`) and which belong to one
  feature. `app/schemas.py`'s docstring promises "API response models and the ingest Diff
  structure", but the module holds only `Diff`.

The sibling change `unify-refresh-orchestration` adds a timeseries refresh module and assumes that
an `app/timeseries/` package already exists to hold it. This change creates that package.

## What Changes

- New package `app/timeseries/`, created with history-preserving moves:
  - `app/ingest.py` → `app/timeseries/ingest.py`
  - `app/models.py` → `app/timeseries/models.py` (`Source`, `Entity`, `Observation` only)
  - `app/schemas.py` → `app/timeseries/diff.py` (holds `Diff`; the misleading docstring is fixed)
  - `app/geojson.py` → `app/timeseries/geojson.py` (timeseries is its only importer; see design)
  - `app/collectors/` → `app/timeseries/collectors/`
- `Base` moves to a new feature-neutral module, `app/orm.py`. It does not go into `app/db.py`,
  because that module creates the async engine at import time. Timeseries, news and events models
  and `alembic/env.py` import `Base` from `app.orm`.
- `alembic/env.py` imports `app.timeseries.models` explicitly. Today the timeseries tables reach
  `Base.metadata` only as a side effect of importing `Base` from the timeseries file. The new import
  keeps `target_metadata` holding the same set of tables.
- The `Diff` broadcast payload, its `{topic: "timeseries", type: "diff"}` message shape, the API
  routes and the database schema are unchanged. No migration.
- No compatibility shims at the old import paths. Every import in `app/`, `tests/` and
  `alembic/env.py` is updated.
- `pyproject.toml` replaces the hand-maintained `[tool.setuptools] packages` list with
  `[tool.setuptools.packages.find]` limited to `app` and `app.*`. Without this, the list would have
  to gain `app.timeseries` and `app.timeseries.collectors` and drop `app.collectors`.
- `app/api/timeseries.py` stays in `app/api/`, following the existing one-router-module-per-feature
  convention.
- `AGENTS.md`, `docs/*-api.md` and module docstrings are updated to the new paths. AGENTS.md
  heading text, including the `#adding-a-data-source` anchor that `CONTRIBUTING.md` links to, stays
  the same.

Nothing changes at runtime. The only observable difference is that Python module paths change for
anyone importing `app.models`, `app.ingest`, `app.schemas`, `app.geojson` or `app.collectors`, and
nothing outside this repo does.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `project-documentation`: the README-sources requirement names `app/collectors/__init__.py`'s
  `build_collectors()` as the source of truth, and that path moves. The AGENTS.md accuracy
  requirement gains a scenario: the module paths AGENTS.md names for the timeseries pipeline and
  the shared `Base` must exist.

## Impact

- **Moved:** `app/ingest.py`, `app/models.py`, `app/schemas.py`, `app/geojson.py`,
  `app/collectors/` (5 modules).
- **New:** `app/timeseries/__init__.py`, `app/orm.py`.
- **Import updates:** `app/scheduler.py`, `app/api/timeseries.py`, `app/news/models.py`,
  `app/events/models.py`, the collectors' own cross-imports, `alembic/env.py`, and the tests
  `test_ingest.py`, `test_ingest_helpers.py`, `test_api_timeseries.py`, `test_bbox.py`,
  `test_geojson.py`, `test_schemas.py`, `test_live_signals.py`, `test_collectors_base.py`,
  `test_hc911_normalize.py`, `test_hc911_helpers.py`, `test_epb.py`, `test_tdot.py` and
  `test_tnaw.py`.
- **Packaging:** `pyproject.toml` `[tool.setuptools]` section. No dependency change. `uv.lock` is
  unaffected; `uv lock --check` confirms this.
- **Docs:** `AGENTS.md` (architecture walkthrough, "Source-agnostic data model", "Adding a data
  source", the GeoJSON convention line), `docs/hc911-api.md`, `docs/tdot-smartway-api.md`,
  `docs/epb-outage-api.md` and `docs/tnaw-advisory-api.md`.
- **Overlaps:** open PR #269 (`fix-alembic-schema-drift`) and most of the sibling refactor changes
  edit the moved files. See design.md for how they interact and the recommended landing order.
