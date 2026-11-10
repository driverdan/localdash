## 0. Preconditions

- [x] 0.1 Confirm siblings 1–10 (`ingest-owns-entity-status` through `extract-spa-serving`) have merged, or record which have not and why landing now is acceptable (see design.md "Sequencing")
- [x] 0.2 Branch from current `main`, run `uv sync --locked --extra dev`, and re-measure: `uv run ruff check . --extend-select UP,B,SIM,BLE,RUF100 --statistics` and the mypy config from design.md §2. Note any large deviation from design.md's counts in the PR description

## 1. Ruff rule set and mechanical rewrite (commit 1, pure)

- [x] 1.1 In `pyproject.toml` `[tool.ruff.lint]`, set `select = ["E4", "E7", "E9", "F", "I", "UP", "B", "SIM", "BLE", "RUF100"]` and update the comment above it. Add `[tool.ruff.lint.flake8-bugbear] extend-immutable-calls = ["fastapi.Depends"]`
- [x] 1.2 Run exactly `uv run ruff check . --fix` and `uv run ruff format .`, with no hand edits. Commit together with 1.1, recording the command in the commit body and noting "on conflict: take the other side and re-run"
- [x] 1.3 Check that the commit removed the six unneeded `# noqa: BLE001` comments (`app/scheduler.py` ×4, `app/events/geocoding.py`, `app/events/ingest.py`, or wherever siblings moved those handlers)

## 2. Manual lint fixes (commit 2)

- [x] 2.1 `app/api/timeseries.py` `_bbox_filter`: `raise HTTPException(...) from None` (B904)
- [x] 2.2 `app/news/fetcher.py` per-feed handler: add `# noqa: BLE001 — a broken feed must not kill the cycle` (or log with `log.exception` if a traceback is wanted; pick one and keep the persisted status unchanged)
- [x] 2.3 Give the remaining `BLE001` suppressions (`app/ws.py`, `app/redaction.py` ×2, `app/api/root.py`, `tests/test_api_routes.py`) a reason if they lack one
- [x] 2.4 `app/news/clustering.py` SIM102 ×2: collapse the nested `if`s, or keep them with a reasoned `noqa` if collapsing hurts readability
- [x] 2.5 Tests: `zip(..., strict=True)` in `tests/test_events_geocoding.py` (B905 ×3); narrow `pytest.raises(Exception)` to the concrete exception in `tests/test_collectors_base.py` and `tests/test_weather.py` (B017 ×2)
- [x] 2.6 `alembic/script.py.mako`: emit `from collections.abc import Sequence` and `str | None` / `str | Sequence[str] | None` annotations so new migrations pass `UP` unchanged
- [x] 2.7 `uv run ruff check .` and `uv run ruff format --check .` are clean

## 3. Type checker (commit 3)

- [x] 3.1 Add `"mypy>=2.4.1,<2.5.0"` to the `dev` extras (bounded-range convention) and run `uv lock`
- [x] 3.2 Add the `[tool.mypy]` block and `feedparser.*` / `apscheduler.*` override from design.md §2. The `disallow_any_generics = false` line carries its reason
- [x] 3.3 Annotate every function `uv run mypy` reports as `no-untyped-def`, including `ingest(session: AsyncSession, ...)`, `_geom_value`, `_observation(..., now: datetime, ..., geom: ...)`, and the `_entry_*(entry)` helpers in `app/news/fetcher.py` (type `entry` as `feedparser.FeedParserDict` or a narrow `Mapping[str, Any]`)
- [x] 3.4 Replace bare `frozenset` in `app/news/clustering.py` with `frozenset[str]`, and `list[list]` in `app/events/ingest.py` with a typed tuple or small dataclass (if `decompose-events-upsert` hasn't already)
- [x] 3.5 Fix the non-annotation errors on their merits, not with `# type: ignore`: `str | None` URL in `app/weather/service.py`, `dict | None` access in `app/api/timeseries.py`, `Any | None` key in `app/collectors/tdot.py`, `Tag | None` return in `app/events/ingest.py`, the BeautifulSoup `AttributeValueList` unions in `chattzoo.py`/`fetcher.py`, `carcruisefinder.py`'s `None` dict, the `set.add` value idiom in `app/events/geocoding.py`. Use `cast(CursorResult, ...)` for `rowcount`. Any unavoidable ignore names its error code
- [x] 3.6 In `app/events/ingest.py`, drop `import datetime as dt` in favour of the existing `from datetime import ...` (design.md §6)
- [x] 3.7 `uv run mypy` reports zero errors; `uv run pytest` passes (no behavior change)

## 4. Hook, CI, docs (commit 4)

- [x] 4.1 `.pre-commit-config.yaml`: replace the `astral-sh/ruff-pre-commit` repo with `local` `ruff-check` / `ruff-format` hooks running `uv run --locked --extra dev ruff ...` (design.md §4); update the header comment. Verify fix-then-abort still holds by staging a file with a fixable issue
- [x] 4.2 `frontend/package.json`: add `"format:check": "prettier --check ."`; confirm `npm run format:check` passes on `main` (format first in its own commit if not)
- [x] 4.3 `.github/workflows/tests.yml`: add a `lint` job (`needs: changes`, `if: needs.changes.outputs.python == 'true'`, same `setup-python`/`setup-uv` pins as `pytest`, `uv sync --locked --extra dev`, then `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`), with a comment explaining why it is tool-native rather than `pre-commit run --all-files`
- [x] 4.4 `.github/workflows/tests.yml`: add `npm run format:check` to the `frontend` job; add `lint` to the `docker` job's `needs` and mention it in the guard comment
- [x] 4.5 `AGENTS.md` "Linting & formatting (pre-commit)": describe the widened rule set and `RUF100`; that the hook runs the locked ruff via `uv run` (needs `uv` on `PATH`); delete the "Keep the hook's ruff `rev` in step" instruction; replace the "Known gap … CI job is deferred" text with the CI enforcement; add `uv run mypy` alongside the `svelte-check` paragraph (whole-project, not in the hook)
- [x] 4.6 `AGENTS.md` "CI" bullet list: add the `lint` job and the `format:check` step in `frontend`; note `lint` runs on the `python` category
- [x] 4.7 `AGENTS.md` Tech stack / dev setup: mention mypy in the dev extras and `uv run mypy` in the local-dev command block; add a short note on typing expectations for new `app/` code (annotated signatures, no bare `# type: ignore`)
- [x] 4.8 `CONTRIBUTING.md` "Linting and formatting": `uv sync --extra dev` comment lists mypy; add the `uv run mypy` command; replace "treat it as a convenience rather than a hard gate" with the CI enforcement note
- [x] 4.9 Grep `AGENTS.md`, `CONTRIBUTING.md`, `README.md` and `.pre-commit-config.yaml` for `ruff-pre-commit`, `rev`, "deferred", and "no CI backstop" and fix any stale text

## 5. Verification

- [x] 5.1 `pre-commit run --all-files` passes with the new local hooks
- [x] 5.2 Staging a file with a `timezone.utc` use aborts the commit with the rewrite applied; staging a bare `except Exception: pass` aborts with `BLE001`
- [x] 5.3 CI on the PR: `lint`, `pytest`, `frontend`, `docker` all run and pass
- [x] 5.4 `openspec validate tighten-python-tooling --strict` passes
- [x] 5.5 PR description lists the manual post-merge step: the repo owner adds `lint` to the required status checks
