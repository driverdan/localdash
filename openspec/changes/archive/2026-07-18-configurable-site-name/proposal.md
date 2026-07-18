## Why

The site's name is hardcoded in three places that already disagree — the header reads
`Chattanooga LocalDash (beta)`, the browser tab reads `LocalDash`, and the FastAPI docs title
reads `LocalDash`. Anyone forking or re-deploying the dashboard has to hunt down and edit
multiple files (and rebuild the frontend) to rebrand it. There should be one source of truth,
changeable at deploy time, shown consistently everywhere.

## What Changes

- Add a single `SITE_NAME` environment variable (default `LocalDash`) as the one source of truth
  for the user-facing site name, read only by the backend at process start.
- The FastAPI application title reads `SITE_NAME` instead of the hardcoded `"LocalDash"`.
- The backend injects `SITE_NAME` into `index.html` **at serve time** (in the existing static-file
  serving seam), so the value is configurable at `docker run` time without a frontend rebuild:
  - the `<title>` tag reflects the configured name, and
  - a synchronous `window.__SITE_NAME__` global is injected so the app reads it at first paint.
- The Svelte header `<h1>` reads the injected `window.__SITE_NAME__` instead of a hardcoded string
  (no extra fetch, no flash). The current `"Chattanooga "` prefix and `" (beta)"` suffix collapse
  into the single configured value.
- `docker-compose.yml` documents/wires the `SITE_NAME` environment variable on the app service.

Non-goals: technical identifiers (the `localdash` DB name/user, the `LocalDash/0.1` outbound
user-agent, the `localdash.*` localStorage prefix, the npm package name, the GitHub footer URL)
are out of scope — those are rename/fork operations, not "the site name," and changing the
localStorage prefix would silently discard users' saved preferences.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `app-shell`: the app introduces a configurable site-name setting; the FastAPI application title
  and the served `index.html` (title tag + injected global) derive from it at runtime.
- `frontend-shell`: the header and browser-tab title display the runtime-configured site name
  rather than hardcoded strings.

## Impact

- **Config**: `app/config.py` gains a `site_name` setting (env `SITE_NAME`, default `LocalDash`).
- **Backend**: `app/main.py` — `FastAPI(title=...)` reads the setting; `NoCacheStaticFiles`
  injects the name when serving `index.html` (covers both `GET /` and the SPA fallback).
- **Frontend**: `frontend/index.html` carries injectable placeholders; `frontend/src/App.svelte`
  reads `window.__SITE_NAME__`.
- **Ops**: `docker-compose.yml` app-service `environment` gains `SITE_NAME`.
- No database, migration, or API-schema changes. No new dependencies.
