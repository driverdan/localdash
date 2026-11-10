## 1. Shared `Base`

- [ ] 1.1 Create `app/orm.py` containing only `class Base(DeclarativeBase)` and a docstring saying it is the declarative base every feature's models register on. It must not import `app.db` or `app.config`
- [ ] 1.2 Change `app/news/models.py` and `app/events/models.py` to `from app.orm import Base`

## 2. Move the timeseries modules (`git mv`; edit only imports and docstrings)

- [ ] 2.1 Create `app/timeseries/__init__.py` with a feature docstring in the style of `app/news/__init__.py`: what the feature is, and the pipeline collectors → ingest → `Diff` on the bus, served by `app/api/timeseries.py`. No re-exports
- [ ] 2.2 `git mv app/models.py app/timeseries/models.py`. Remove `class Base` and the `DeclarativeBase` import, import `Base` from `app.orm`, and keep the module docstring
- [ ] 2.3 `git mv app/ingest.py app/timeseries/ingest.py`
- [ ] 2.4 `git mv app/schemas.py app/timeseries/diff.py`. Change the docstring to describe only the `Diff` ingest-result / bus-message type
- [ ] 2.5 `git mv app/geojson.py app/timeseries/geojson.py`
- [ ] 2.6 `git mv app/collectors app/timeseries/collectors`
- [ ] 2.7 Inside the moved files, update imports to `app.timeseries.collectors[.base]`, `app.timeseries.geojson`, `app.timeseries.models` and `app.timeseries.diff`. This covers `ingest.py`, `collectors/__init__.py`, `collectors/hc911.py`, `tdot.py`, `epb.py` and `tnaw.py`
- [ ] 2.8 Update the path in `collectors/base.py`'s docstring ("see app/collectors/__init__.py") and in `collectors/__init__.py`'s docstring if it names a path

## 3. Other importers

- [ ] 3.1 `app/scheduler.py`: import `build_collectors`, `BaseCollector`, `ingest` and `Source` from their `app.timeseries.*` modules
- [ ] 3.2 `app/api/timeseries.py`: import the GeoJSON helpers and `Entity`/`Observation`/`Source` from `app.timeseries.geojson` / `app.timeseries.models`
- [ ] 3.3 `alembic/env.py`: replace `from app.models import Base` with `from app.orm import Base` plus `import app.timeseries.models  # noqa: F401`, with a comment that the import registers the timeseries tables on `Base.metadata`. Do not add news or events imports here (PR #269's scope)
- [ ] 3.4 Grep for leftovers: `grep -rnE "app\.(models|ingest|schemas|geojson|collectors)\b" app tests alembic` and `grep -rnE "app/(models|ingest|schemas|geojson)\.py|app/collectors" --include=*.py --include=*.md . | grep -v openspec/` both return nothing outside this change's own artifacts

## 4. Packaging

- [ ] 4.1 In `pyproject.toml`, replace `[tool.setuptools] packages = [...]` with `[tool.setuptools.packages.find]` `include = ["app", "app.*"]`
- [ ] 4.2 `uv lock --check` passes (no lock change expected)
- [ ] 4.3 Build a wheel (`uv build --wheel` into a scratch directory) and confirm it contains `app/timeseries/`, `app/timeseries/collectors/`, `app/orm.py`, `app/news/`, `app/events/sources/`, `app/weather/` and `app/api/`, and no `tests/` or `alembic/`

## 5. Tests

- [ ] 5.1 Update imports in `tests/test_ingest.py`, `tests/test_ingest_helpers.py`, `tests/test_api_timeseries.py`, `tests/test_bbox.py`, `tests/test_geojson.py`, `tests/test_live_signals.py`, `tests/test_collectors_base.py`, `tests/test_hc911_normalize.py`, `tests/test_hc911_helpers.py`, `tests/test_epb.py`, `tests/test_tdot.py` and `tests/test_tnaw.py`
- [ ] 5.2 `git mv tests/test_schemas.py tests/test_diff.py` and import `Diff` from `app.timeseries.diff`
- [ ] 5.3 Add `tests/test_orm.py` with one pure test. After importing `app.timeseries.models`, `app.news.models` and `app.events.models`, all three use the same `app.orm.Base` (each model's `metadata is Base.metadata`), and `Base.metadata.tables` holds `sources`, `entities`, `observations`, `news_articles` and `events`. This pins down the one non-mechanical change, `Base` moving
- [ ] 5.4 Run the full suite: `pytest`, against `docker compose up -d db`
- [ ] 5.5 Run `pytest tests/test_news_db.py` and `pytest tests/test_events_ingest.py` each on their own, so nothing depends on the timeseries mappers being loaded as a side effect
- [ ] 5.6 Run `ruff check` and `ruff format --check` on the touched files (the pre-commit hook does this). Import sorting (`I`) will reorder the moved imports

## 6. Documentation

- [ ] 6.1 `AGENTS.md` "The central idea: snapshot → time-series": name `app/timeseries/collectors/`, `app/timeseries/ingest.py` and `app/scheduler.py` in the intro and in steps 1–4. Say that ingest returns a `Diff` (`app/timeseries/diff.py`)
- [ ] 6.2 `AGENTS.md` "Non-obvious decisions": the `observed_at` bullet's `(ingest.py)` becomes `app/timeseries/ingest.py`
- [ ] 6.3 `AGENTS.md` "Source-agnostic data model (`models.py`)": change the heading's path to `app/timeseries/models.py` and keep the heading's words. Add one line that the shared declarative `Base` lives in `app/orm.py` and that every feature's models register on it
- [ ] 6.4 `AGENTS.md` "Adding a data source": `app/timeseries/collectors/<name>.py` and `app/timeseries/collectors/__init__.py`'s `build_collectors()`. Keep the heading text unchanged so the `CONTRIBUTING.md` anchor `#adding-a-data-source` still resolves
- [ ] 6.5 `AGENTS.md` API conventions: the GeoJSON bullet points at `app/timeseries/geojson.py` and notes that a second geo feature should promote the generic helpers to a shared module rather than import timeseries internals
- [ ] 6.6 `AGENTS.md` "What this is" / feature list: add a short note under Timeseries that its code lives in `app/timeseries/` (router in `app/api/timeseries.py`), matching how news, events and weather name their packages
- [ ] 6.7 `docs/hc911-api.md` (links to `../app/collectors/hc911.py` and `../app/ingest.py`), `docs/tdot-smartway-api.md`, `docs/epb-outage-api.md` and `docs/tnaw-advisory-api.md` (`collectors/<name>.py` headings and links): update the paths and fix the in-page anchor in `docs/tdot-smartway-api.md` if its heading text changes
- [ ] 6.8 Check that `README.md` and `CONTRIBUTING.md` name none of the old paths (neither did at proposal time)

## 7. Final check

- [ ] 7.1 `docker compose up --build` starts, migrations run, and `/map` loads entities and receives live diffs
- [ ] 7.2 `openspec validate move-timeseries-into-package --strict` passes
