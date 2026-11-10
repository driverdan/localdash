## Why

`app/models.py` holds two things: the shared SQLAlchemy `DeclarativeBase` and the timeseries
tables (`Source`/`Entity`/`Observation`). This causes three problems:

- `app/news/models.py:26`, `app/events/models.py:30` and `alembic/env.py:13` all import `Base` from
  the timeseries models file. As a result, importing news or events models also loads the
  timeseries mappers.
- `alembic/env.py` sets `target_metadata = Base.metadata`. The timeseries tables reach that
  metadata only because they share a file with `Base`. The news and events tables never reach it,
  because env.py never imports their modules.
- Two smaller problems: `app/schemas.py`'s docstring promises "API response models and the ingest
  Diff structure", but the module holds only `Diff`. And `pyproject.toml`'s
  `[tool.setuptools] packages` list is hand-maintained, so every new package must be remembered
  there. Forgetting one fails nothing visibly (see design).

A larger version of this change, which moved all timeseries code into an `app/timeseries/`
package, was considered and dropped. The backend is treated as one application, with no mandated
separation between backend feature packages (see the sibling `relax-backend-feature-separation`).
What remains here is the part worth doing regardless of package layout.

## What Changes

- New module `app/orm.py` holding only `Base`. `app/models.py` (the timeseries models, still at
  that path), `app/news/models.py` and `app/events/models.py` import `Base` from it.
- `alembic/env.py` imports `Base` from `app.orm` and explicitly imports every model module:
  `app.models`, `app.news.models` and `app.events.models`. No table reaches `target_metadata` by
  sharing a file with `Base`. As a result, the news and events tables are now included in that
  metadata. Nothing reads it today (migrations are hand-written SQL), so nothing observable
  changes.
- `app/schemas.py` is renamed to `app/diff.py`, with a docstring that describes only `Diff`.
  `Diff` and its `{topic: "timeseries", type: "diff"}` message are unchanged.
- `pyproject.toml` replaces the hand-maintained package list with
  `[tool.setuptools.packages.find]` limited to `app` and `app.*`.
- Imports are updated in `app/`, `tests/` and `alembic/env.py`. No compatibility shim is left at
  `app/schemas.py`.
- `AGENTS.md` names `app/orm.py` as the home of the shared `Base` and `app/diff.py` as the home of
  `Diff`.

Not changing: `app/ingest.py`, `app/models.py`'s timeseries models, `app/geojson.py`,
`app/collectors/`, the API, the database schema (no migration), WebSocket payloads and log names.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `project-documentation`: the "AGENTS.md matches the shipped app" requirement gains a scenario
  saying AGENTS.md names the module that defines the shared declarative `Base`.

## Impact

- **New:** `app/orm.py`.
- **Renamed:** `app/schemas.py` → `app/diff.py`; `tests/test_schemas.py` → `tests/test_diff.py`.
- **Edited imports:** `app/models.py`, `app/news/models.py`, `app/events/models.py`,
  `app/ingest.py`, `alembic/env.py` and `tests/test_live_signals.py`.
- **New test:** `tests/test_orm.py`.
- **Packaging:** `pyproject.toml` `[tool.setuptools]` section. No dependency change, so `uv.lock`
  is unaffected.
- **Docs:** `AGENTS.md` (data-model section and the architecture walkthrough's `Diff` mention).
- **Overlaps:** open PR #269 (`fix-alembic-schema-drift`) edits `app/models.py`,
  `app/events/models.py` and `alembic/env.py`. See design.md.
