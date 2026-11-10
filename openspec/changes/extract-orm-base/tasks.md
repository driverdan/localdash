## 1. Shared `Base`

- [x] 1.1 Create `app/orm.py` containing only `class Base(DeclarativeBase)` and a docstring saying every model module registers its tables on it. It must not import `app.db` or `app.config`
- [x] 1.2 In `app/models.py`, remove `class Base` and the `DeclarativeBase` import and add `from app.orm import Base`. Keep the timeseries models and the module docstring
- [x] 1.3 Change `app/news/models.py` and `app/events/models.py` to `from app.orm import Base`

## 2. Alembic

- [x] 2.1 In `alembic/env.py`, replace `from app.models import Base` with `from app.orm import Base` plus side-effect imports of `app.models`, `app.news.models` and `app.events.models` (`# noqa: F401`). Add a comment that model modules register their tables on `Base` only when imported
- [x] 2.2 Check that `alembic upgrade head` still runs. The DB test fixture runs it in a subprocess, and it can also be run by hand against `docker compose up -d db`

## 3. Rename `schemas.py`

- [x] 3.1 `git mv app/schemas.py app/diff.py`. Change the docstring to describe only the `Diff` ingest-result / bus-message type
- [x] 3.2 Update `app/ingest.py` to `from app.diff import Diff`
- [x] 3.3 `git mv tests/test_schemas.py tests/test_diff.py` and update its import. Update the import in `tests/test_live_signals.py`
- [x] 3.4 `grep -rnE "app\.schemas|app/schemas|from app\.models import Base" app tests alembic AGENTS.md README.md CONTRIBUTING.md docs` returns nothing

## 4. Packaging

- [x] 4.1 In `pyproject.toml`, replace `[tool.setuptools] packages = [...]` with `[tool.setuptools.packages.find]` `include = ["app", "app.*"]`
- [x] 4.2 `uv lock --check` passes (no lock change expected)
- [x] 4.3 Build a wheel (`uv build --wheel` into a scratch directory) and confirm it contains `app/`, `app/api/`, `app/collectors/`, `app/news/`, `app/events/`, `app/events/sources/` and `app/weather/`, including `app/orm.py` and `app/diff.py`, and no `tests/` or `alembic/`

## 5. Tests

- [x] 5.1 Add `tests/test_orm.py` with one pure test. After importing `app.models`, `app.news.models` and `app.events.models`, all three use the same `app.orm.Base` (each model's `metadata is Base.metadata`), and `Base.metadata.tables` holds `sources`, `entities`, `observations`, `news_articles` and `events`
- [x] 5.2 Run the full suite: `pytest`, against `docker compose up -d db`
- [x] 5.3 Run `pytest tests/test_news_db.py` and `pytest tests/test_events_ingest.py` each on their own, so nothing depends on the timeseries mappers being loaded as a side effect
- [x] 5.4 Run `ruff check` and `ruff format --check` on the touched files (the pre-commit hook does this)

## 6. Documentation

- [x] 6.1 `AGENTS.md` "Source-agnostic data model (`models.py`)": add one line saying the shared declarative `Base` lives in `app/orm.py`, every feature's models register on it, and `alembic/env.py` imports each model module explicitly
- [x] 6.2 `AGENTS.md` architecture walkthrough, step 3: "returns a `Diff` (`new`/`updated`/`closed`)" names `app/diff.py`

## 7. Final check

- [x] 7.1 `docker compose up --build` starts, migrations run, and `/map` loads entities and receives live diffs
- [x] 7.2 `openspec validate extract-orm-base --strict` passes
