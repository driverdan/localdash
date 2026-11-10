## Context

Current state:

| Module | Contents | Imported by |
|---|---|---|
| `app/models.py` | `Base` + `Source`, `Entity`, `Observation` | `app/ingest.py`, `app/scheduler.py`, `app/api/timeseries.py`, `app/news/models.py` (`Base`), `app/events/models.py` (`Base`), `alembic/env.py` (`Base`), tests |
| `app/schemas.py` | `Diff` only (docstring also promises "API response models") | `app/ingest.py`, `tests/test_schemas.py`, `tests/test_live_signals.py` |

Constraints and findings:

- `app/db.py` calls `get_settings()` and `create_async_engine(...)` at import time. Anything that
  imports it gets an engine, and `alembic/env.py` currently avoids it.
- `alembic/env.py` sets `target_metadata = Base.metadata`. Today that metadata holds the timeseries
  tables only, as a side effect of importing `Base` from the file that defines them. Migrations are
  hand-written SQL, so nothing reads `target_metadata` today. Open PR #269 would start reading it
  with `alembic check`.
- No test patches `app.schemas` or `app.models.Base` by dotted string, so every reference that
  must change is an ordinary `import` statement.
- Packaging: the Dockerfile's `deps` stage runs `uv sync --locked --no-editable`, which installs a
  real copy of the listed packages into `/app/.venv`. The runtime stage then copies the `app/`
  source tree to `/app`, and both entry points put `/app` first on `sys.path`:
  `uvicorn app.main:app` adds the working directory, and `alembic.ini` sets
  `prepend_sys_path = .`. The source tree therefore shadows the installed copy. A package missing
  from the hand-maintained list breaks neither Docker, CI (editable install) nor local dev. It only
  leaves the installed copy incomplete, and nothing reports it. That silence is why the hand list
  is worth replacing.

## Goals / Non-Goals

**Goals:**

- The declarative `Base` lives in a feature-neutral module that creates no engine.
- `alembic/env.py` registers every model module by explicit import. No table depends on sharing a
  file with `Base`.
- The module that holds `Diff` is named for what it holds.
- New packages under `app/` are packaged without editing a list.
- No change to runtime behaviour, schema, API, WebSocket payloads or log names.

**Non-Goals:**

- Moving timeseries code into an `app/timeseries/` package (considered and dropped; see
  decision 1).
- Renaming `app/models.py`. It keeps the timeseries models at its current path.
- `alembic check`, `include_object` and model/migration alignment. Those belong to PR #269.
- Typed response models (`add-typed-contracts`) and dead columns (`remove-dead-schema`).

## Decisions

### 1. The full package move was considered and dropped

The first version of this change moved `app/ingest.py`, `app/models.py`, `app/schemas.py`,
`app/geojson.py` and `app/collectors/` into a new `app/timeseries/` package. The reason was
symmetry with `app/news/`, `app/events/` and `app/weather/`. The user has since decided that the
backend is one application, with no mandated separation between backend feature packages. The
sibling change `relax-backend-feature-separation` records that guideline. Frontend import rules
and `/api/v1/<feature>/` URL namespacing are unaffected. Without the symmetry argument, the move
is churn: it would rename five modules and conflict textually with most of the sibling refactors.
The pieces kept here are the ones that are worth doing whatever the package layout is.

### 2. `Base` goes to a new `app/orm.py`

`app/orm.py` contains only the `DeclarativeBase` subclass and a docstring saying that every
model module registers on it.

*Alternatives considered:*

- **`app/db.py`.** Importing a model would then create the async engine and read settings,
  `alembic/env.py` would build an asyncpg engine it never uses, and any test that imports a model
  would touch the engine. Rejected.
- **Leave `Base` in `app/models.py`.** That keeps news and events models, and Alembic, depending
  on the timeseries models file, along with its import-time side effect.
- **An `app/db/` package (`base.py` + `session.py`).** It would also rewrite every
  `from app.db import ...` site, which is outside this change.

`app/models.py` keeps its name and its module docstring ("the source-agnostic geo time-series
schema"), which already describes it correctly once `Base` is gone.

### 3. `alembic/env.py` imports all three model modules

```python
# Every model module registers its tables on Base only when imported.
import app.events.models  # noqa: F401
import app.models  # noqa: F401
import app.news.models  # noqa: F401
from app.orm import Base
```

`target_metadata` now holds every table the migrations create, not just the timeseries ones.
Nothing reads `target_metadata` today: there is no autogenerate and no `alembic check` on `main`.
So this widens the metadata without changing anything observable. The model modules import only
SQLAlchemy, GeoAlchemy2 and `app.orm`, not `app.db`, so env.py still creates no async engine.

*Alternative:* import only `app.models`, which preserves exactly today's metadata. That still
leaves news and events missing, and #269 has to add them anyway for `alembic check` to work. Doing
it here makes env.py correct on its own terms, and it reduces #269's env.py hunk to its
`include_object` filter.

### 4. `app/schemas.py` becomes `app/diff.py`

The module holds one dataclass: an ingest result and its bus message. `diff.py` names it
accurately and fixes the docstring. It also frees `schemas.py`, the conventional name for Pydantic
response models, for `add-typed-contracts`, so `Diff` and those models cannot be confused.
`tests/test_schemas.py` becomes `tests/test_diff.py` so the test file still names the module it
tests. No `app/schemas.py` shim is left behind: three internal importers do not justify one.

### 5. `pyproject.toml` uses package discovery

```toml
[tool.setuptools.packages.find]
include = ["app", "app.*"]
```

The `include` filter keeps `tests`, `alembic` and the rest of the repo root out of the package.
The discovered set is the same as today's list, so the built wheel does not change. The
implementation confirms this by building a wheel and listing its contents. `uv.lock` records no
package list, but `uv lock --check` must still pass. `[tool.ruff]` is not touched.

*Alternative:* keep the hand list. It is correct today, but it is a trap for the next package,
and the trap makes no noise when it springs (see Context).

## Interaction with open PR #269 (`fix-alembic-schema-drift`)

#269, open and untouched since 2026-10-14, adds `alembic check` to CI and aligns models with
migrations. Here is how it overlaps with this change, file by file:

- `app/models.py`: #269 edits index declarations and `spatial_index` on `Entity`/`Observation` and
  appends a module-level `Index("ix_obs_source_time", ...)`. This change removes `class Base` and
  the `DeclarativeBase` import near the top of the file. The hunks are separate, so a rebase
  either way should apply cleanly or need only trivial resolution of the import block.
- `app/events/models.py`: #269 adds an `Index` import and `__table_args__` on `Event`. This change
  edits only the `from app.models import Base` line, about ten lines away. No conflict is
  expected.
- `alembic/env.py`: #269 adds `import app.events.models` / `import app.news.models` next to
  `from app.models import Base` and adds an `include_object` filter. This change rewrites that
  same import block, so **it conflicts.** Resolution: keep this change's four-line import block,
  which already contains #269's two imports, drop #269's duplicates, and keep its docstring
  addition and `include_object` filter unchanged.
- `AGENTS.md`: #269 edits the CI and Migrations sections. This change edits the data-model
  section. #269 was written against a pre-`isolate-test-database` AGENTS.md and needs a rebase
  anyway.

After this change, #269's premise holds: every feature's tables are on the metadata
`alembic check` compares. **Recommendation:** do not block on #269. If it is revived first, land
it first; this change's edits are mechanical and cheap to redo. Otherwise land this change and
rebase #269 using the resolution above.

## Sibling changes

Without the package move, the textual overlaps listed in the first version mostly disappear.
What remains:

- **`relax-backend-feature-separation`** lands first and records why this change does not move
  code. It edits AGENTS.md. This change adds one line to the data-model section and touches the
  `Diff` mention in the architecture walkthrough, so any overlap should be small.
- **`unify-refresh-orchestration`** originally assumed an `app/timeseries/` package would exist for
  its timeseries refresh module. It has since been revised to put that cycle in a top-level
  `app/collect.py`, so it no longer depends on this change. The only overlap left is that its
  tests import `Diff` from `app.diff` once this change has landed.
- **`ingest-owns-entity-status`** edits `app/ingest.py`, and this change edits that file's
  `from app.schemas import Diff` line. A conflict is possible only if it also edits the import
  block, and is trivial to resolve.
- **`add-typed-contracts`** may type `Diff` or add response models. It should import `Diff` from
  `app.diff` and is free to use `app/schemas.py` for Pydantic models.
- **`remove-dead-schema`** edits `Source` and the relationships in `app/models.py`. This change
  edits only the top of that file. No conflict is expected.
- **`tighten-python-tooling`** edits `pyproject.toml`, but `[tool.ruff]`, a different table. Its
  type checker will see `app/orm.py` and `app/diff.py`, which needs no coordination.

No other sibling touches these files. This change has no ordering dependency on any sibling and
can land at any point after `relax-backend-feature-separation`. Landing it early keeps the
`app/schemas.py` rename out of the way of `add-typed-contracts`.

## Risks / Trade-offs

- [Importing `app.news.models` or `app.events.models` no longer loads the timeseries mappers as a
  side effect] → No relationship crosses features, so nothing should rely on that side effect. To
  confirm, run `tests/test_news_db.py` and `tests/test_events_ingest.py` each on their own. In a
  full run, other modules load the timeseries models first and would hide the problem.
- [env.py now imports the news and events models, which could pull in heavier imports during
  migrations] → Both modules import only SQLAlchemy, GeoAlchemy2 and `app.orm`. The test fixture
  runs `alembic upgrade head` in a subprocess on every DB-backed run, so this is exercised by the
  suite.
- [A missed `app.schemas` import breaks app start-up] → `tests/test_api_routes.py` imports
  `app.main`. A grep for `app.schemas` and `from app.models import Base` must return nothing.

## Migration Plan

No data or deployment migration. The image is rebuilt as usual. Rollback is a plain revert.

## Open Questions

- Is `app/orm.py` the preferred name for the `Base` module? (Alternatives: `app/db_base.py`, or a
  later `app/db/` package.)
