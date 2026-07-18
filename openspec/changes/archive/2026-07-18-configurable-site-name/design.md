## Context

The user-facing site name is hardcoded in three places today, already inconsistent:

- `frontend/index.html` → `<title>LocalDash</title>` (static, built by Vite into `static/`)
- `frontend/src/App.svelte:44` → `<h1>Chattanooga LocalDash (beta)</h1>` (baked into the JS bundle)
- `app/main.py:77` → `FastAPI(title="LocalDash", ...)` (read by Python at process start)

Two runtimes are involved. The frontend is a Vite SPA built at **image-build time** (Dockerfile
`frontend` stage) and served unchanged by FastAPI's static mount. The backend reads environment
variables at **container-run time**. The requirement is that the name be configurable at
`docker run` time — so the value cannot be baked into the frontend build; it must be applied by the
only thing that runs at container start with access to the environment: the Python process.

A key existing seam makes this cheap: `app/main.py`'s `NoCacheStaticFiles.get_response` is the single
choke point through which every `index.html` serve flows — both `GET /` and the SPA fallback
(`get_response("index.html", scope)` at `app/main.py:55`). There is also an existing
`/api/v1/config` bootstrap endpoint, but it is fetched asynchronously and only by `MapView`.

## Goals / Non-Goals

**Goals:**

- One environment variable, `SITE_NAME` (default `LocalDash`), as the sole source of truth.
- Configurable at `docker run` time — a restart with a new value suffices, no frontend rebuild.
- Correct `<title>` and header `<h1>` at first paint (no flash, no extra network round-trip).
- Consistent value across the browser tab, the header, and the FastAPI docs title.

**Non-Goals:**

- Changing technical identifiers: the `localdash` DB name/user, the `LocalDash/0.1` outbound
  user-agent strings, the `localdash.*` localStorage key prefix, the npm package name, or the
  GitHub footer URL. These are fork/rename concerns; touching the localStorage prefix would also
  silently discard users' saved preferences.
- Per-user or per-request variation — the name is fixed for a process's lifetime.
- Localization / separate "city" vs "name" knobs.

## Decisions

### Decision: Inject at serve time in `NoCacheStaticFiles`, not at build time

The frontend build runs before the runtime environment exists, so a Vite-baked value
(`%VITE_SITE_NAME%` / `import.meta.env`) would freeze the name into the image and require a rebuild
to change — violating the run-time-configurability goal. Instead the backend substitutes the value
into `index.html` as it is served, inside the existing `get_response` seam. Because that seam serves
`index.html` for both `GET /` and every SPA fallback, a single implementation covers all entry
points.

*Alternatives considered:*

- **Vite build-time templating** — simplest markup, but only changeable by rebuilding the image
  (rejected: fails the run-time goal).
- **Entrypoint `sed`/`envsubst` on the static file** — works at run time but mutates a shipped
  asset on disk, adds a shell templating step, and has restart-vs-recreate subtleties (a plain
  container restart keeps the already-substituted file). Rejected in favor of keeping the logic in
  Python where the config already lives.
- **Async fetch of the name from `/api/v1/config` and `document.title =`** — reuses an existing
  pipe but introduces a visible flash of the default title/header before the fetch resolves, plus a
  second round-trip. Rejected for the flash.

### Decision: Expose the value to the bundle via a synchronous `window.__SITE_NAME__` global

To render the header `<h1>` correctly at first paint without a fetch, the injected HTML defines
`window.__SITE_NAME__` in a small inline script before the module bundle loads (mirroring the
existing pre-paint theme bootstrap script's placement). `App.svelte` reads it synchronously. This
keeps the name out of the async `/api/v1/config` path entirely and guarantees the header and tab
title agree.

*Alternative considered:* adding `site_name` to `/api/v1/config` and binding it in Svelte — rejected
for the same flash/round-trip reason; the config endpoint stays tiles-only.

### Decision: Placeholder tokens in `index.html`, substituted server-side

`index.html` carries explicit placeholder tokens (e.g. a distinctive token in the `<title>` and an
inline `window.__SITE_NAME__ = "…"` assignment) that the backend string-replaces with the
HTML/JS-escaped configured name. Substitution targets tokens, not the previous value, so it is
idempotent and safe regardless of default. The templated bytes can be computed once per process
(the value is constant for the process lifetime) and reused; responses keep the existing
`Cache-Control: no-cache`.

### Decision: `site_name` setting in `app/config.py`; FastAPI title reads it

`Settings` gains `site_name: str = "LocalDash"` (env `SITE_NAME` via the existing
pydantic-settings config). `app/main.py` uses `get_settings().site_name` for `FastAPI(title=…)` and
for the injection. Single read path, no drift.

## Risks / Trade-offs

- **HTML/JS injection safety** → The configured name is operator-supplied and interpolated into both
  an HTML text node (`<title>`) and a JS string literal (`window.__SITE_NAME__`). Escape it for both
  contexts (HTML-escape for the title; JSON-encode for the script literal) so a name containing
  `<`, `"`, or `</script>` cannot break out. It is trusted-operator input, but escaping is cheap and
  correct.
- **Losing the static `index.html` 304 path** → Serving `index.html` through a substitution step
  means hand-building the response rather than deferring entirely to `StaticFiles`. Mitigation: the
  mount already forces `Cache-Control: no-cache` on every response, so ETag/304 for `index.html` was
  not a meaningful optimization; asset responses are unaffected.
- **Placeholder must survive the Vite build** → The token sits in `frontend/index.html`, which Vite
  copies to `static/index.html`; a spec scenario asserts the built file still contains it, guarding
  against a future build change that would strip or rewrite it.
- **Restart required to change the name** → Because the value is read at process start, changing
  `SITE_NAME` needs a container restart (not a rebuild). This is the intended trade-off and far
  cheaper than the build-time alternative.

## Migration Plan

Additive and backward-compatible: with `SITE_NAME` unset the FastAPI title stays `LocalDash` and the
header/tab show `LocalDash`. The only visible change to the existing deployment is that the header
drops the `Chattanooga ` prefix and ` (beta)` suffix; set `SITE_NAME="Chattanooga LocalDash (beta)"`
to preserve the old header verbatim. No database or API-schema changes; rollback is reverting the
diff.
