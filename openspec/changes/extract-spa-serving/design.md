## Context

`app/main.py` on `main` (143 lines) does three jobs:

1. **Process setup at import** (lines 26-29): `logging.basicConfig(level=logging.INFO)` and
   `install_log_redaction()`.
2. **SPA serving** (lines 31-110):
   - `STATIC_DIR`.
   - `SITE_NAME_TOKEN`.
   - `_js_string`, which builds a JS string literal that cannot break out of a `<script>` element.
   - `_index_html`, which is `lru_cache`d, reads `STATIC_DIR / "index.html"`, and substitutes
     `get_settings().site_name` into both placeholder spots.
   - `NoCacheStaticFiles`, which closes WebSocket scopes, serves the injected index for
     `""`/`"."`/`"index.html"`, falls back to the injected index on an extension-less non-`api`
     404, and stamps `Cache-Control: no-cache` on every response.
3. **Wiring**: the lifespan, `FastAPI(title=get_settings().site_name, ...)`, the router includes
   (the weather router is gated on `get_settings().weather_enabled` at import), and the static
   mount, which comes last.

Job 2 is the only part that is not wiring. Moving it out has no conflicts with the rest of the
file.

Two facts limit what can be tested today:

- `_index_html()` ignores the `directory` the class was built with and always reads the
  module-level `STATIC_DIR`. It also reads the site name from global settings behind a
  process-wide cache. As a result, `NoCacheStaticFiles(directory=tmp_path)` cannot serve a test
  `index.html`, and a test cannot pick the site name without clearing two caches.
- Existing coverage is thin:
  - `tests/test_api_routes.py::test_api_paths_never_fall_back_to_spa` calls `get_response`
    directly for `api`, `api/` and `api/nope` on a `tmp_path` instance. It only works because those
    paths raise before the index is read.
  - `tests/test_api_routes.py::test_live_ws_is_global_not_feature_scoped` exercises the WebSocket
    close indirectly and asserts only that the connection is not accepted.
  - `tests/test_api_routes.py::test_old_flat_routes_are_gone` passes through the static mount (the
    old `/api/...` paths 404 there).
  - `tests/test_redaction.py::test_app_installs_redaction` depends on the import-time
    `install_log_redaction()` in `main.py`. This change does not touch it.
  - Nothing tests the `no-cache` header, the `/map` fallback, the missing-asset 404, site-name
    injection, or `_js_string`'s escaping.

The import-time side effects that the review raised:

- `main.py` mounts `StaticFiles(directory=STATIC_DIR)` at import. Starlette's `check_dir=True`
  raises `RuntimeError` if the directory is missing. This is why CI runs `mkdir -p static` before
  pytest (`.github/workflows/tests.yml:114-119`; AGENTS.md CI section).
- `main.py` calls `get_settings()` at import for the title and the weather gate.
- `app/db.py:11-14` builds the engine at import. This is why `tests/conftest.py` overrides
  `DATABASE_URL` before any `app.*` import (AGENTS.md testing section; `test-isolation` spec).

## Goals / Non-Goals

**Goals:**

- `app/main.py` is wiring only. SPA serving lives in `app/spa.py`, which has no `app.*` imports.
- Every static-mount behaviour in the `app-shell` spec has a direct, offline test that does not
  import `app.main`.
- No observable HTTP behaviour change.

**Non-Goals:**

- An app factory (`create_app(settings)`). Decision 3 weighs it and recommends against it for
  this change.
- Making the DB engine in `app/db.py` lazy.
- Moving `logging.basicConfig` / `install_log_redaction()` out of import time.
- Dropping CI's `mkdir -p static`.
- Changing the uvicorn target, `docker-entrypoint.sh`, or the frontend's placeholder tokens.

## Decisions

### 1. A new module `app/spa.py`, with the mount call left in `main.py`

`app/spa.py` holds `STATIC_DIR`, `SITE_NAME_TOKEN`, `_js_string` and `NoCacheStaticFiles`. Their
docstrings and comments move with them. `main.py` keeps the mount, last, with its existing
comment:

```python
app.mount(
    "/",
    NoCacheStaticFiles(directory=STATIC_DIR, html=True, site_name=settings.site_name),
    name="static",
)
```

Here `settings` is whatever `main.py` already uses for the title. Binding it once as
`settings = get_settings()` is fine, and so is calling `get_settings()` again.

`STATIC_DIR` is computed as `Path(__file__).resolve().parent.parent / "static"`. That expression
gives the same path from `app/spa.py` as from `app/main.py`, because both files are in `app/`.

*Alternatives:*

- A `mount_spa(app, settings)` helper in `spa.py`. This hides the ordering rule ("mounted last so
  `/api` wins") inside another module, while the ordering is a wiring decision that should stay
  next to the router includes.
- Putting the module under `app/api/`. Every module there is an `APIRouter` for one feature
  namespace, and this is not a router.
- Naming the module `app/static.py`. That reads like the `static/` directory. "spa" names the
  responsibility: serving the single-page app.

The class keeps its name. `NoCacheStaticFiles` undersells it, but renaming it touches the existing
test import for no behavioural gain. Implementation may rename it if the reviewer prefers.

### 2. Two small testability changes inside the moved code

These are the only edits beyond moving code. Neither one changes what a browser sees.

- **The site name is a constructor argument** (`site_name: str`, keyword-only). `spa.py` then has
  no `get_settings()` call, so tests pass a hostile name directly. `main.py` already reads settings
  at import for the title, so this adds no new global lookup. It overlaps in spirit with
  `inject-settings-and-clock` (sibling 6), which passes settings values in rather than looking
  them up. This change does the injection for `spa.py`, so sibling 6 needs nothing here.
- **The index is read from `self.directory` and cached on the instance.** The module-level
  `lru_cache`d `_index_html()` becomes a method (for example `_index_html(self)`). On first use it
  reads `Path(self.directory) / "index.html"`, substitutes the name, and stores the result on the
  instance. The current code silently reads `STATIC_DIR` whatever directory the instance was given,
  which is a latent bug for any second instance. Production has exactly one instance over
  `STATIC_DIR`, so it still reads one file once per process. Rendering stays lazy, not done in
  `__init__`: an empty `static/`, as in CI, must not fail at import, which matches today's
  behaviour.

The `__call__` override gains Starlette's `Scope`/`Receive`/`Send` annotations while it moves.
This is free here, and it keeps `tighten-python-tooling` (sibling 11) from having to touch the new
file.

*Alternative:* a pure move that keeps the `lru_cache` and the `get_settings()` call. Tests would
then have to monkeypatch `app.spa.STATIC_DIR`, monkeypatch settings, and call `cache_clear()` in
fixture teardown. That works, but it is more fragile than the two changes above, and it leaves the
directory bug in place.

### 3. App factory: recommended out

The question was whether to replace the module-level `app` with `create_app(settings) -> FastAPI`,
and move `basicConfig`, redaction install, the settings reads and the mount into that function.

Two shapes are possible:

- **(a) A factory plus `app = create_app()` at module level.** The uvicorn target `app.main:app`,
  `docker-entrypoint.sh`, and `from app.main import app` in `tests/test_api_routes.py` all keep
  working. However, importing `app.main` still builds the app, so every import-time side effect
  remains, and CI still needs `mkdir -p static`. The only gain is that a test could build a second
  app with different settings (for example with weather disabled). No test does that today.
- **(b) Factory only, served with `uvicorn --factory app.main:create_app`.** This removes the
  side effects in `main.py`, but has these costs:
  - `docker-entrypoint.sh`, the `uvicorn app.main:app --reload` lines in `AGENTS.md` and
    `CONTRIBUTING.md`, and every developer's muscle memory change.
  - `tests/test_api_routes.py` needs a fixture that builds the app.
  - `tests/test_redaction.py::test_app_installs_redaction` has to be rewritten, because importing
    the app would no longer install redaction. Redaction would then depend on the factory being the
    entrypoint.

  Even then, CI can drop `mkdir -p static` only if the factory also takes the static directory as
  a parameter and tests pass a temporary one. Making the mount tolerate a missing directory
  (`check_dir=False`) does not work. Starlette then raises `RuntimeError` on the first request that
  reaches the mount, and that includes the `/api/...` 404s that `test_old_flat_routes_are_gone`
  relies on.

  Option (b) also leaves the side effect that actually constrains the test suite: `import app.main`
  imports `app.db`, which builds the engine. The `conftest.py` ordering rule therefore stays.

The factory would trade a small, well-documented annoyance (a one-line CI `mkdir` and import-time
settings reads) for a change to the deploy entrypoint and two test rewrites, with no user-facing
gain. Extracting `spa.py` costs nothing toward a later factory. If one is ever wanted, for example
to test the weather-disabled router set, the factory would be about 15 lines of wiring, because the
SPA code is no longer in the way.

### 4. The DB engine stays eager

A lazy engine would not change the `conftest.py` ordering rule much. The rule exists so that every
`SessionLocal` user sees the test URL. A lazy engine would only move the moment the URL is read
from "first import" to "first session". It would also touch every `from app.db import SessionLocal`
caller. This is out of scope.

### 5. Spec delta: add the two behaviours no spec states

The `no-cache` header and the WebSocket close ship today but appear in no spec. That is why a
refactor could drop them without a failing spec scenario or test. This change adds one `app-shell`
requirement for both (see `specs/app-shell/spec.md`) and backs every scenario with a test. The
existing requirements "SPA fallback for client-side routes" and "Runtime site-name injection into
served index.html" are already accurate and stay as they are. The `frontend-shell` requirement
"Build output served by the existing static mount" refers to the fallback as "owned by
`app-shell`" and needs no change.

## Tests

New file `tests/test_spa.py`. It is offline and does not import `app.main`, so it needs neither
`static/` nor the DB. It builds a bare `Starlette`/`FastAPI` app containing one dummy `/api/v1/ping`
route and a `NoCacheStaticFiles(directory=tmp_path, html=True, site_name=...)` mount. `tmp_path`
holds a fixture `index.html` with both placeholders, and `assets/app.js`. Tests:

- `GET /` returns the injected index with `<title>` and `window.__SITE_NAME__` set, plus
  `Cache-Control: no-cache`.
- `GET /map` and a nested `GET /events/123` return the same injected index with `no-cache`.
- `GET /index.html` returns the injected copy, not the raw placeholder file.
- `GET /assets/app.js` returns the raw file with `no-cache` and no injection.
- `GET /assets/missing.js` returns 404.
- `GET /api`, `/api/` and `/api/nope` return 404 and do not include `index.html`. This replaces the
  direct-`get_response` check through a real ASGI request.
- A hostile site name, for example `</script><script>alert(1)</script> & "q"`, is HTML-escaped in
  `<title>` and arrives as a JS string with `<`/`>`/`&` escapes. A direct unit test
  of `_js_string` covers the same escapes.
- The index file is read once per instance. Rewrite `index.html` after the first request, and the
  second response is unchanged.
- A WebSocket connect to an unmatched path is not accepted. Use `TestClient(...).websocket_connect`
  and expect `WebSocketDisconnect`.

Existing tests:

- `test_api_paths_never_fall_back_to_spa` changes its import to `app.spa`, or it can be folded
  into `test_spa.py`. The implementation can choose.
- `test_live_ws_is_global_not_feature_scoped` and `test_old_flat_routes_are_gone` stay as they are,
  as end-to-end checks that the real `main.py` mount is still last.

## Overlap with sibling changes

The siblings are listed in the suggested landing order. This change is number 10.

- `unify-refresh-orchestration` (4) rewrites the lifespan's use of `build_scheduler()` in
  `main.py`. The edits are in different lines of the same file. Whichever change lands second
  rebases, and there is no semantic dependency.
- `inject-settings-and-clock` (6): see Decision 2. `spa.py` takes its one setting as an argument.
  If sibling 6 lands first and edits `_index_html` in `main.py`, carry its form across in the move.
- `tighten-python-tooling` (11) may tighten ruff rules or add a type checker. The moved code is
  annotated (Decision 2). If 11 lands first, `spa.py` must pass whatever it enables.
- `consolidate-shared-helpers` (7): `_js_string` has no duplicate in `app/` (grep for `u003c` and
  `html.escape`), so nothing is shared.
- `tidy-small-inconsistencies` (13): no known overlap. `main.py` defines no logger.

## Risks / Trade-offs

- [Risk] The move silently changes which `index.html` is served. → `STATIC_DIR` resolves to the
  same path from `app/spa.py`. A task confirms it equals the old path, and a manual check through
  the rebuilt compose stack (`GET /` and `GET /map`) confirms it end to end.
- [Risk] Per-instance caching renders the index twice if two instances exist. → Only one instance
  exists in production. Tests build their own instances, which is the point of the change.
- [Trade-off] Two small non-move edits (Decision 2) make the diff more than a pure move. → Both are
  confined to `spa.py`, are listed in the proposal, and are covered by the new tests.
- [Trade-off] The import-time side effects that motivated part of the review stay. → Decision 3
  documents why, so the question does not need to be reopened from scratch.

## Migration Plan

This is a code-only refactor with no data, config or deploy change. Roll back by reverting the PR.

## Open Questions

- Should `NoCacheStaticFiles` be renamed (for example to `SpaStaticFiles`) during the move? The
  default is no (Decision 1).
- Should `test_api_paths_never_fall_back_to_spa` move into `tests/test_spa.py` or stay in
  `test_api_routes.py` with an updated import? Either works.
