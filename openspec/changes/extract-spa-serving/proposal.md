## Why

`app/main.py` is 143 lines, and lines 31-110 are not application wiring. They hold the SPA serving
code: `STATIC_DIR`, `SITE_NAME_TOKEN`, `_js_string`, `_index_html`, and the `NoCacheStaticFiles`
class. That class sets `Cache-Control: no-cache`, falls back to `index.html` for extension-less
non-`/api` paths, injects the site name into `index.html`, and closes stray WebSocket upgrades. The
entrypoint should read as "configure logging, build the lifespan, include routers, mount the
frontend". At the moment it also carries an HTML-escaping helper and a `StaticFiles` subclass.

The serving code is also barely tested. Only one test exercises it directly
(`tests/test_api_routes.py::test_api_paths_never_fall_back_to_spa`). Nothing checks the `no-cache`
header, the fallback for a client route, the 404 for a missing asset, or site-name injection and
its escaping. The WebSocket close is covered only indirectly. Part of the reason is that
`_index_html` always reads the module-level `STATIC_DIR` and the global settings, so a test cannot
point the class at a temporary directory and a known site name.

## What Changes

- Move the SPA serving code out of `app/main.py` into a new module, `app/spa.py`: `STATIC_DIR`,
  `SITE_NAME_TOKEN`, `_js_string`, and `NoCacheStaticFiles` with its index rendering. `main.py`
  keeps one `app.mount("/", ...)` line, still last, so `/api` still wins.
- Two small changes to the moved code make it testable. Behaviour in production is unchanged:
  - `NoCacheStaticFiles` takes the site name as a constructor argument. `main.py` passes
    `get_settings().site_name`, which it already reads for the app title. `app/spa.py` does not
    look up settings itself.
  - The injected `index.html` is read from the directory the instance was given, not from the
    module-level `STATIC_DIR`. It is rendered once per instance on first use. This replaces the
    module-level `lru_cache`. In production there is one mount over `STATIC_DIR`, so the file read
    and the "computed once per process" behaviour stay the same.
- Add direct tests for every static-mount behaviour, run against a temporary directory with a
  fixture `index.html`.
- Add the two static-mount behaviours that no spec states yet to the `app-shell` spec: the
  `no-cache` revalidation header and the clean close of WebSocket upgrades that reach the mount.
  Both already ship. This change only makes them part of the spec.
- Update `AGENTS.md` where it says the SPA fallback lives in `main.py`.

**Not changing**: the app factory question (see design.md, Decision 3: recommended **out**), the
import-time `logging.basicConfig` / `install_log_redaction()` calls, the import-time
`get_settings()` reads in `main.py`, and the import-time engine in `app/db.py`. CI keeps its
`mkdir -p static` step. There is no observable HTTP behaviour change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `app-shell`: adds one requirement, "Static mount revalidation and non-HTTP requests". It states
  the `Cache-Control: no-cache` header on every response from the static mount and the clean close
  of WebSocket upgrades that reach it. Both behaviours exist today but no requirement states them.
  The existing "SPA fallback for client-side routes" and "Runtime site-name injection into served
  index.html" requirements are unchanged.

## Impact

- `app/main.py`: loses about 80 lines and the `html`, `json`, `functools.lru_cache`,
  `StaticFiles`, `HTTPException`, `HTMLResponse`/`Response` and `Scope` imports. Its docstring
  stays accurate.
- `app/spa.py`: new module. It depends only on Starlette/FastAPI and the standard library, with no
  `app.*` imports.
- `tests/test_api_routes.py`: `test_api_paths_never_fall_back_to_spa` imports from `app.spa`.
- `tests/test_spa.py`: new offline tests (no DB, and no import of `app.main`).
- `AGENTS.md`: the frontend paragraph (line 101) and the API conventions bullet (lines 526-529)
  name `main.py` as the home of the SPA fallback. The CI paragraph (lines 309-310) stays
  accurate, because `main.py` still mounts `static/` at import.
- `.github/workflows/tests.yml`: comment only, if at all. The step stays.
- No new dependencies. No change to `docker-entrypoint.sh`, the uvicorn target `app.main:app`, the
  Dockerfile, or the frontend.
