## Context

This is one of thirteen changes proposed in parallel from a Python architecture review. The
current state, measured on `origin/main` at `cf2ed4a`:

- **Ruff config.** `[tool.ruff.lint] select = ["E4", "E7", "E9", "F", "I"]` and `target-version
  = "py314"`. `ruff format --check .` is clean (130 files). `openspec/` is excluded.
- **Stale suppressions.** There are eleven `# noqa: BLE001` comments: four in `app/scheduler.py`,
  two in `app/redaction.py`, one each in `app/ws.py`, `app/events/geocoding.py`,
  `app/events/ingest.py` and `app/api/root.py`, and one in `tests/test_api_routes.py`. With the
  current rule set, `RUF100` reports all eleven as "non-enabled". Even with `BLE` enabled, six of
  them stay unused: the four in `scheduler.py`, `geocoding.py:108` and `events/ingest.py:439`.
  `BLE001` already exempts handlers that call `log.exception(...)` or re-raise. Turning on `BLE`
  adds one unsuppressed hit, at `app/news/fetcher.py:284`, which is the per-feed catch that logs
  with `log.warning`.
- **Ruff version drift.** The hook pins `rev: v0.17.2`, while `uv.lock` has ruff `0.17.3` (bumped
  by Dependabot #310, which doesn't touch `.pre-commit-config.yaml`). #324 (0.17.4) is open.
  AGENTS.md asks contributors to keep the two in step by hand, and that rule is already broken.
  The main checkout's `.venv` has ruff `0.16.10`, which is a separate, local staleness.
- **No type checker** in the dev extras or CI. Ruff reports 14 `ANN201` hits in `app/` (811 `ANN`
  hits across `app` + `tests`).
- **CI.** `.github/workflows/tests.yml` has `changes`, `pytest`, `frontend` and `docker` jobs.
  Nothing runs ruff, `ruff format` or prettier. AGENTS.md says a CI `pre-commit run --all-files`
  job "is deferred to a later change".
- **Mixed datetime imports.** `app/events/ingest.py:12,15` imports both `datetime as dt` and
  `from datetime import datetime, timedelta, timezone`. Across modules, the `app/events/` package
  uses `import datetime as dt` (8 modules) and the rest of `app/` uses `from datetime import ...`
  (17 modules).

### Ruff fallout, measured

These counts come from ruff 0.17.2 (the pre-commit-cached binary that matches the hook). The
0.16.10 venv binary gave the same counts for `app tests`. They are reported per scope because the
CI job lints the whole tree (`.`), which includes `alembic/`.

`ruff check app --select UP` (the review's figure, confirmed):

| Rule  | Hits | Fix |
|-------|-----:|-----|
| UP017 | 44 | auto |
| UP037 | 6  | auto |
| UP035 | 2  | auto |

`ruff check . --extend-select UP,B,SIM,BLE,RUF100`, with
`flake8-bugbear.extend-immutable-calls = ["fastapi.Depends"]`:

| Rule   | Hits | Fix | Where |
|--------|-----:|-----|-------|
| UP017  | 63 | auto | `app` 44, `tests` 19 |
| UP007  | 27 | auto | `alembic/versions/*` (3 per migration header) |
| UP035  | 11 | auto | `app` 2, `alembic/versions/*` 9 |
| UP037  | 6  | auto | `app` |
| RUF100 | 6  | auto | the six unneeded `BLE001` suppressions above |
| SIM905 | 1  | auto | `app/news/textutil.py:13` |
| B905   | 3  | manual | `tests/test_events_geocoding.py` (`zip` without `strict=`) |
| B017   | 2  | manual | `tests/test_collectors_base.py:20`, `tests/test_weather.py:248` (`pytest.raises(Exception)`) |
| SIM102 | 2  | manual | `app/news/clustering.py:175,183` |
| BLE001 | 1  | manual | `app/news/fetcher.py:284` |
| B904   | 1  | manual | `app/api/timeseries.py:43` (`raise HTTPException` inside `except ValueError`) |
| **Total** | **123** | 114 auto / 9 manual | auto-fix touches 47 files, about 131 changed lines |

Without the `Depends` exemption there would be 9 more `B008` hits, all FastAPI `Depends(...)`
defaults in `app/api/{events,news,timeseries}.py`. These are the framework's idiom, not a bug.

### Type-checker fallout, measured

All three candidates ran against the existing venv's site-packages (Python 3.14.6,
SQLAlchemy 2.1.4, Pydantic 2.14.1, GeoAlchemy2 0.20.0), through `uvx` with no project venv
created:

| Checker | Config | `app/` | `app/` + `tests/` |
|---------|--------|-------:|-------:|
| mypy 2.4.1 | default | 24 errors / 11 files | 81 errors / 27 files (`--check-untyped-defs`) |
| mypy 2.4.1 | `strict`, `disallow_any_generics = false`, pydantic plugin, stub-less imports ignored | **67 errors / 19 files** | — |
| mypy 2.4.1 | full `strict` | 145 (76 of them `type-arg`, mostly bare `-> dict`) | — |
| pyright 1.1.414 | basic | 15 errors | 87 errors |
| ty 0.0.100 | default | 24 diagnostics | 107 diagnostics |

The 67 under the proposed config break down as 34 `no-untyped-def`, 10 `no-any-return`, and 23
others: 5 `arg-type`, 4 `union-attr`, 4 `attr-defined`, 3 `return-value`, 2 `assignment` and
singles. The files with the most are `app/news/registry.py` (6, all from untyped source dicts),
`app/events/sources/cityspark.py` (6), `app/events/ingest.py` (6) and `app/news/fetcher.py` (4).
The untyped defs are concentrated in `app/api/timeseries.py` (8), `app/news/fetcher.py` (6) and
`app/ingest.py` (4). A cold run takes about 5 s.

Several of the 23 non-annotation errors are worth reading rather than silencing:
`app/weather/service.py:152` passes a `str | None` URL to `httpx.AsyncClient.get`;
`app/api/timeseries.py:169-170` calls `.get` and indexes a `dict | None`;
`app/collectors/tdot.py:39` uses an `Any | None` as a dict key; `app/events/ingest.py:53-54`
returns `Tag | None` as `Tag`. Two are SQLAlchemy typing gaps (`Result.rowcount`, which needs
`CursorResult`), and one is an idiom (`seen.add(x)` used as a value in `geocoding.py:43`).

## Goals / Non-Goals

**Goals:**

- A ruff rule set that catches real bug classes (`B`, `BLE`), keeps idioms current for the
  `py314` target (`UP`), and makes every `noqa` both meaningful and needed (`RUF100`).
- A type checker that gates `app/` at a strictness the current code can reach in one change.
- One ruff version, the locked one, used by the hook, a manual `uv run ruff` and CI.
- Lint, format and type errors fail CI, closing the gap AGENTS.md records.

**Non-Goals:**

- `ANN`, `D`, `PL`, the full `RUF` set, or other rule families.
- Type-checking `tests/` (81 errors today) or `alembic/`.
- `disallow_any_generics` (76 more errors, mostly `-> dict` returns that `add-typed-contracts`
  replaces).
- One `datetime` import style across the codebase. Only the within-file mix is fixed.
- Running the type checker in the commit hook.
- Refactoring the code that mypy flags beyond what the type fix needs. Behavior changes belong to
  the siblings.

## Decisions

### 1. Rule set: add `UP`, `B`, `SIM`, `BLE`, `RUF100`

- **`UP` (pyupgrade).** 107 hits, all auto-fixable, no judgment calls. With `target-version =
  "py314"` it keeps annotations and imports current (`datetime.UTC`, `X | Y`,
  `collections.abc`).
- **`B` (bugbear).** This is where real bugs show up (`B904` lost exception context, `B905`
  silent `zip` truncation, `B006`/`B008` mutable or call defaults). The one framework false
  positive, FastAPI `Depends`, is handled with `extend-immutable-calls`, not per-line `noqa`.
  Switching to `Annotated[..., Depends()]` would also fix it, but that is a refactor outside this
  change.
- **`SIM`.** Three hits. It's cheap now and stops nested-`if` and similar noise from growing.
  `SIM102` in `clustering.py` may read better nested. If so, the implementer either collapses it
  or adds a reasoned `noqa`, and `RUF100` keeps that `noqa` honest.
- **`BLE`, not deleting the comments.** The broad catches in this codebase are deliberate: a
  scheduler tick, a feed or a WebSocket must not take down the loop. Enabling `BLE` turns those
  comments into reviewed exceptions and flags new silent catch-alls. Deleting the comments would
  leave nothing to catch the next `except Exception: pass`.
- **`RUF100`.** This is the root cause of the finding: a suppression that names a disabled rule,
  or one that isn't needed, goes unreported. It auto-fixes, and here it removes 6 of the 10
  `app/` `BLE001` comments.
- **Not `ANN`.** mypy's `disallow_untyped_defs` covers the same ground for `app/` and also checks
  that the annotations are correct. `ANN` would double-report and would flag 700+ test
  functions.

Alternative considered: enable one family per change, starting with `UP`. That was rejected
because every enable means another whole-tree rewrite that conflicts with in-flight branches. One
batch, sequenced last, conflicts once.

### 2. Type checker: mypy, `strict` minus `disallow_any_generics`, on `app/`

Configured in `pyproject.toml`:

```toml
[tool.mypy]
python_version = "3.14"
files = ["app"]
strict = true
disallow_any_generics = false   # revisit after add-typed-contracts; +76 errors today
plugins = ["pydantic.mypy"]

[[tool.mypy.overrides]]
module = ["feedparser.*", "apscheduler.*"]   # no stubs / py.typed
ignore_missing_imports = true
```

Why mypy:

- **It installs and locks like ruff.** It's a pure-Python wheel in the `dev` extras, pinned by
  `uv.lock`, run with `uv run mypy`. Pyright's PyPI package is a wrapper that downloads a Node
  runtime and the pyright npm package on first use. That happens outside `uv.lock`, and every
  cold CI run makes a network fetch.
- **It's mature for this stack.** The models already use SQLAlchemy 2.0 `Mapped[...]`, which mypy
  understands without the deprecated SQLAlchemy plugin. The Pydantic plugin types
  `BaseSettings` constructors and validators. GeoAlchemy2 produced no errors.
- **ty is not ready to gate on yet.** At 0.0.100 it is still pre-1.0, and its diagnostics change
  between releases. Its counts here are comparable to mypy's, and it would match the Astral
  toolchain, so it is worth revisiting at 1.0. Switching later costs one config block.
- Pyright's lower count (15 at "basic") reflects a looser default, not better code. It is not a
  reason to choose it.

Why this strictness: full `strict` costs 145 errors, and 76 of them are `type-arg` on bare
`dict`/`list` returns. Many of those are API payload dicts that `add-typed-contracts` turns into
Pydantic models, so fixing them here would be wasted work. The remaining strict flags
(`disallow_untyped_defs`, `warn_return_any`, `no_implicit_reexport` and so on) cost 43 on top of
the default 24. That is a one-change job, and it fixes the loose signatures the review named.

Why `app/` only: tests are 81 errors at `--check-untyped-defs`, mostly fakes passed where real
types are expected. Typing them is a separate change. `alembic/` is migration scripts.

### 3. Where each tool runs

| Tool | Commit hook | CI | Manual |
|------|-------------|----|--------|
| `ruff check --fix` / `ruff format` | yes (staged files, fix-then-abort) | `ruff check .` + `ruff format --check .` | `uv run ruff ...` |
| mypy | **no** | yes | `uv run mypy` |
| prettier | yes | `npm run format:check` in `frontend` job | `npm run format` |
| svelte-check | no | yes (unchanged) | `npm run check` |

mypy stays out of the hook for the reasons already recorded for `svelte-check`. It checks the
whole project, so a staged-files run either misses cross-module errors or checks everything on
every commit. It also needs the project's dependencies installed, which pre-commit's isolated
environments don't provide.

### 4. Ruff hook reads the lock: `local` hook via `uv run --locked --extra dev`

```yaml
- repo: local
  hooks:
    - id: ruff-check
      name: ruff check
      language: system
      entry: uv run --locked --extra dev ruff check --fix
      types_or: [python, pyi]
      require_serial: true
    - id: ruff-format
      name: ruff format
      language: system
      entry: uv run --locked --extra dev ruff format
      types_or: [python, pyi]
      require_serial: true
```

This follows the pattern the prettier hook already uses (`local` + `system`, reusing the repo's
own toolchain). The hook, CI and a manual `uv run ruff` then all use the `uv.lock` version, so
Dependabot's uv ecosystem keeps the hook current, and #324-style bumps can no longer drift from
the hook. Because the python filter includes `uv.lock`, a ruff bump PR runs the new `lint` job,
which shows any new findings on that PR.

`--locked` matches CI: if `pyproject.toml` was edited without `uv lock`, the hook fails instead of
re-locking as a side effect of committing. `--extra dev` makes `uv run` install ruff and mypy into
a venv that was synced without extras.

Alternative considered: keep `ruff-pre-commit` and add the `pre-commit` Dependabot ecosystem or
a CI check that compares `rev` to `uv.lock`. Either way there would still be two pins plus a
mechanism to keep them equal, where this has one pin.

### 5. Close the CI gap now, with tool-native checks rather than `pre-commit run --all-files`

The new rules only hold if something enforces them. Without CI, `--no-verify`, an uninstalled
hook, or an agent worktree without hooks lets violations in, and the next contributor's hook
"fixes" unrelated lines in their commit.

- A new **`lint`** job runs when `needs.changes.outputs.python == 'true'`: `setup-python`,
  `setup-uv` (same pins as `pytest`), `uv sync --locked --extra dev`, then `uv run ruff check .`,
  `uv run ruff format --check .` and `uv run mypy`. It needs no database service, so it fails
  faster than `pytest`.
- The **`frontend`** job gains `npm run format:check` (`prettier --check .`), a new script in
  `frontend/package.json`.
- The **`docker`** job adds `lint` to `needs`. The existing `!cancelled() && !failure()` guard
  already treats a skipped job as satisfied.

Why not one `pre-commit run --all-files` job: the hooks run in fix mode, while CI wants check
mode. That one job would need Python, uv and Node at once, and it would ignore the per-category
path filtering, running prettier on Python-only PRs and ruff on frontend-only ones.

`ci-change-filtering`'s category definitions are unchanged. The lint job reads only files the
`python` and `frontend` filters already cover, and `.pre-commit-config.yaml` doesn't affect CI.

### 6. Datetime imports: fix the within-file mix only

`UP017` already rewrites `timezone.utc` to `UTC` everywhere. The remaining inconsistency is
`app/events/ingest.py` using both styles. That file standardizes on `from datetime import ...`,
which is what its non-`dt` code mostly uses. The cross-module split (`dt` in `app/events/`) is
consistent within each package and has a reason: the events code uses `dt.date`, `dt.datetime`
and `dt.time` side by side, and field names like `date` would shadow bare imports. Enforcing one
style with `ICN001`/`ICN003` would rewrite about 25 modules for no bug-finding value.

### 7. Alembic migrations are fixed, and the template too

The 36 `alembic/` hits are `Union[...]` and `typing.Sequence` in the headers generated by
`script.py.mako`. The auto-fix rewrites only annotations of module constants, and Alembic reads
the values, not the annotations. `script.py.mako` is updated to emit `str | None` and
`collections.abc.Sequence`. Otherwise every `alembic revision` would produce a file the hook
rewrites on its first commit.

## Sequencing

This change touches about 47 files mechanically and about 19 for type fixes, so it conflicts
textually with all twelve siblings. **It lands after siblings 1–10** (slot 11 in the suggested
order):

1. `ingest-owns-entity-status`
2. `add-shared-http-client`
3. `move-timeseries-into-package`
4. `unify-refresh-orchestration`
5. `decompose-events-upsert`
6. `inject-settings-and-clock`
7. `consolidate-shared-helpers`
8. `add-typed-contracts`
9. `unify-observation-geometry`
10. `extract-spa-serving`

The reason is the type fixes rather than the ruff rewrite. Most of the 67 mypy errors are in code
the siblings rewrite:

- `app/news/registry.py` (6, untyped source dicts) becomes a dataclass registry in
  `add-typed-contracts` (8). That change also replaces many bare `-> dict` API returns, which is
  why `disallow_any_generics` is deferred.
- `app/ingest.py` (`ingest(session, ...)`, `_geom_value`, `_observation(..., now, ..., geom)`)
  moves in `move-timeseries-into-package` (3), and its `now` and `geom` parameters change in
  `inject-settings-and-clock` (6) and `unify-observation-geometry` (9).
- `app/events/ingest.py` (6 errors, the mixed datetime imports, `list[list]`) is split by
  `decompose-events-upsert` (5).
- `app/weather/service.py:152` and the collectors' HTTP calls change in `add-shared-http-client`
  (2). `app/scheduler.py`, where 4 of the stale suppressions are, is rewritten by
  `unify-refresh-orchestration` (4).
- `app/main.py` (3 untyped defs) is changed by `extract-spa-serving` (10).
- `consolidate-shared-helpers` (7) may move the `_entry_*` helpers or textutil code.

Landing first would mean typing that code and then rewriting it, and the siblings' rebases would
fight the `UP017` rewrite on lines they also touch. **`remove-dead-schema` (12) and
`tidy-small-inconsistencies` (13)** are small, and either order works. If they're still open when
this merges, they rebase and re-run `ruff check --fix`, and the hook enforces that anyway.

Implementation commits:

1. **Ruff config + mechanical rewrite.** The new `[tool.ruff.lint]` settings, then exactly
   `uv run ruff check . --fix` and nothing else. The commit body records the command. On any
   rebase conflict in this commit, take the other side and re-run the command instead of merging
   by hand. Reviewers can check the commit by re-running it.
2. **Manual lint fixes**: the 9 manual hits plus `noqa` reasons.
3. **mypy config + type fixes.**
4. **Hook, CI, `format:check`, docs.**

The numbers above should be measured again at the start of implementation, after the siblings
merge. They are a sizing estimate, not a contract.

## Risks / Trade-offs

- **Every open branch conflicts with the rewrite.** → Land late, keep the mechanical commit pure,
  and resolve conflicts by re-running the fix (see Sequencing).
- **The hook depends on `uv`.** Contributors without `uv` on `PATH` get a failing hook. → `uv` is
  already the documented setup, and the hook's failure message names the missing command.
- **First commit in a fresh worktree creates `.venv`.** `uv run` syncs a project venv on first use,
  which adds a few seconds and some disk use per agent worktree under `.claude/worktrees/`. → It
  is cached afterwards and uses uv's shared wheel cache. Contributors who share one venv can set
  `UV_PROJECT_ENVIRONMENT`.
- **A ruff or mypy upgrade adds findings.** → Both are bounded-range pins in `uv.lock`, and an
  upgrade PR runs the `lint` job, so findings appear on the Dependabot PR rather than on someone
  else's commit.
- **New required check.** Until the repo owner adds `lint` to branch protection, it reports but
  doesn't block. → Called out as a manual post-merge step.
- **mypy false positives on SQLAlchemy result types** (`rowcount`). → Fix with a narrow
  `cast(CursorResult, ...)`, not module-level ignores, and keep `warn_unused_ignores` (part of
  `strict`) on.
- **Stricter commit hook.** Non-fixable `B`, `SIM` or `BLE` errors now abort a commit until fixed
  by hand. → That is the intent. The rule families were chosen for a low false-positive rate,
  and the current tree has 9 such hits.

## Migration Plan

There are no runtime or data changes. Rollback is reverting the PR. After merge, the repo owner
adds `lint` to the required status checks. Existing clones need no re-install, because pre-commit
reads the new hook config on the next commit. Running `uv sync --extra dev` once installs mypy
ahead of time.

Archive phase: when syncing `code-quality-tooling`, also update its Purpose paragraph. It currently
says ruff is provisioned by pre-commit. It should say ruff comes from the locked dev dependencies,
and that the capability now covers mypy and CI enforcement.

## Open Questions

- Should `lint` become a required status check? The recommendation is yes. It's a repo-settings
  change only the owner can make.
- Is `SIM` wanted? It's included for cheapness (3 hits). Dropping it changes nothing else in the
  design.
- Timing for follow-ups: `disallow_any_generics` after `add-typed-contracts`, type-checking
  `tests/`, and revisiting ty at 1.0.
