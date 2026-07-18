## 1. Backend setting

- [ ] 1.1 Add `site_name: str = "LocalDash"` to `Settings` in `app/config.py` (env `SITE_NAME` via the existing pydantic-settings config)
- [ ] 1.2 Change `app/main.py` `FastAPI(title="LocalDash", ...)` to read `get_settings().site_name`

## 2. Runtime injection into index.html

- [ ] 2.1 Add placeholder tokens to `frontend/index.html`: a distinctive token in `<title>` and a pre-paint inline `window.__SITE_NAME__ = "<token>"` assignment (placed like the existing theme bootstrap, before the module bundle)
- [ ] 2.2 In `app/main.py` `NoCacheStaticFiles`, when the served path resolves to `index.html` (covering both `GET /` and the SPA fallback), substitute the tokens with the configured `site_name`, HTML-escaping for the `<title>` and JSON-encoding for the `window.__SITE_NAME__` literal
- [ ] 2.3 Compute the templated `index.html` bytes once per process (value is constant for the process lifetime) and keep the existing `Cache-Control: no-cache` on the response; leave asset and `/api` responses untouched

## 3. Frontend header

- [ ] 3.1 In `frontend/src/App.svelte`, replace the hardcoded `<h1>Chattanooga LocalDash (beta)</h1>` with the value read synchronously from `window.__SITE_NAME__` (add a typing for the global as needed for svelte-check)

## 4. Ops wiring

- [ ] 4.1 Add `SITE_NAME: ${SITE_NAME:-LocalDash}` to the app service `environment` in `docker-compose.yml`, matching the existing interpolated-from-`.env` comment style

## 5. Verify

- [ ] 5.1 `docker compose up --build`; confirm default header/tab/API-docs all read `LocalDash`
- [ ] 5.2 Restart with `SITE_NAME` set to a custom value (including one containing `"` and `<`); confirm header, browser tab, and `/docs` title all show it, escaped correctly, with no flash and no extra network fetch for the name
- [ ] 5.3 Hard-refresh a deep link (e.g. `/map`) and confirm the injected title/global are present on the SPA fallback response
- [ ] 5.4 `npm run check` in `frontend/` passes (svelte-check clean)
