## 1. Extract `app/spa.py`

- [x] 1.1 Create `app/spa.py` with a module docstring, and move in `STATIC_DIR`, `SITE_NAME_TOKEN`, `_js_string` and `NoCacheStaticFiles` from `app/main.py` with their comments and docstrings. Add no `app.*` imports
- [x] 1.2 Give `NoCacheStaticFiles.__init__` a keyword-only `site_name: str` (pass the remaining arguments through to `StaticFiles`), and replace the module-level `lru_cache`d `_index_html()` with an instance method. On first use the method reads `Path(self.directory) / "index.html"`, applies the existing two-step substitution with `self`'s site name, and caches the result on the instance. Keep it lazy, so `__init__` never reads the file
- [x] 1.3 Annotate `__call__` with Starlette's `Scope`, `Receive` and `Send`, and keep `get_response`'s existing annotations
- [x] 1.4 Confirm `app.spa.STATIC_DIR` equals the path `app/main.py` computed before the move (repo-root `static/`)

## 2. Slim `app/main.py`

- [x] 2.1 Delete the moved code, and import `NoCacheStaticFiles` and `STATIC_DIR` from `app.spa`
- [x] 2.2 Pass `site_name=get_settings().site_name` (or a single bound `settings`) to the mount. Keep the mount last, with its "/api wins" comment
- [x] 2.3 Drop the imports that are now unused (`html`, `json`, `lru_cache`, `Path`, `StaticFiles`, `HTTPException`, `HTMLResponse`, `Response`, `Scope`). Leave the logging setup, the redaction install, the lifespan, the router includes, and the uvicorn target `app.main:app` unchanged

## 3. Tests

- [x] 3.1 Add `tests/test_spa.py`, which is offline and does not import `app.main`. Add a fixture that writes an `index.html` containing both placeholders (`<title>__SITE_NAME_PLACEHOLDER__</title>` and `window.__SITE_NAME__ = "__SITE_NAME_PLACEHOLDER__"`) and an `assets/app.js` into `tmp_path`. The fixture builds a bare app with one dummy `/api/v1/ping` route and mounts `NoCacheStaticFiles(directory=tmp_path, html=True, site_name=...)` at `/`, last
- [x] 3.2 Test `GET /` and `GET /index.html`: each returns the injected index with `Cache-Control: no-cache`
- [x] 3.3 Test the SPA fallback: `GET /map` and `GET /events/123` return the injected index with `no-cache`, and `GET /assets/missing.js` returns 404
- [x] 3.4 Test that `GET /assets/app.js` returns the raw file with `no-cache` and that no injection happens
- [x] 3.5 Test that `GET /api`, `/api/` and `/api/nope` return 404 and that the body is not the index, and that `GET /api/v1/ping` still reaches its route
- [x] 3.6 Test a hostile site name (`</script><script>alert(1)</script> & "q"`): the `<title>` is HTML-escaped and the `window.__SITE_NAME__` literal uses the `<`/`>`/`&` escapes. Add a direct unit test of `_js_string`
- [x] 3.7 Test that the index is read once per instance: rewrite `index.html` after the first request and assert that the second response is unchanged
- [x] 3.8 Test that a WebSocket connect to an unmatched path is not accepted (`TestClient(...).websocket_connect` raises `WebSocketDisconnect`)
- [x] 3.9 `tests/test_api_routes.py`: point `test_api_paths_never_fall_back_to_spa` at `app.spa`, or delete it once 3.5 covers it through a real request. Leave `test_live_ws_is_global_not_feature_scoped` and `test_old_flat_routes_are_gone` as end-to-end checks on the real mount

## 4. Docs

- [x] 4.1 `AGENTS.md` frontend paragraph (line 101): the SPA fallback lives in `app/spa.py` and is mounted last by `main.py`
- [x] 4.2 `AGENTS.md` API/frontend conventions bullet (lines 526-529): `main.py` mounts `static/` at `/` last through `app/spa.py`'s `NoCacheStaticFiles`, which owns the SPA fallback, the `no-cache` header and site-name injection
- [x] 4.3 Check that the `AGENTS.md` CI paragraph (lines 309-310) and the `.github/workflows/tests.yml` comment (lines 114-117) are still accurate. `main.py` still mounts `static/` at import, so the `mkdir -p static` step stays. Change wording only if it names the moved code

## 5. Verification

- [x] 5.1 `uv run pytest` passes, including the new `tests/test_spa.py`, which also passes with no `static/` directory present
- [x] 5.2 `uv run ruff check` and `uv run ruff format --check` pass, and the pre-commit hooks pass
- [x] 5.3 `sg docker -c 'docker compose up --build -d'`: `GET /` and `GET /map` return the site-name-injected index with `Cache-Control: no-cache`, `GET /assets/<missing>.js` returns 404, and `GET /api/nope` returns the API's 404
- [x] 5.4 `openspec validate extract-spa-serving --strict` passes
