# Migrate frontend to Svelte 5 + TypeScript

## Why

The dashboard UI is a single 451-line vanilla-JS file (`static/app.js`) whose state/DOM
synchronization plumbing (`refreshAll`, `reconcileSelect`, manual re-renders) already accounts for a
third of the code and grows with every filter or panel added. To prepare for new, unrelated features,
the frontend needs a component framework with reactive state and a feature-namespace organization
mirroring the API's `/api/v1/<feature>/` convention — so a future feature is a new folder plus one
mount point, on both sides of the wire.

## What Changes

- Replace the vanilla JS frontend (`static/app.js`, `static/index.html`, `static/style.css`) with a
  **Svelte 5 + TypeScript** app built by **plain Vite** (not SvelteKit) in a new `frontend/` directory.
- Organize frontend code in **feature namespaces mirroring the API**: `src/features/timeseries/` for
  everything timeseries (including the Leaflet map, which stays with timeseries until a second feature
  needs it), `src/lib/` for feature-agnostic shell code. Features never import from each other; the
  app shell composes features the way `main.py` composes routers.
- Vite builds into `static/` (gitignored build artifact); FastAPI's existing mount serves it unchanged.
- **Docker becomes a multi-stage build**: a Node stage runs `vite build`, the Python stage copies the
  output. Local dev uses `vite dev` with an `/api` proxy to uvicorn.
- Leaflet + markercluster move from CDN `<script>` tags to npm imports (typed).
- **Straight port — no behavior changes.** Same filters, table, detail panel, popups, marker styling,
  clustering, WebSocket live updates, and reconnect behavior as today.
- **BREAKING** (workflow, not runtime): the repo is no longer toolchain-free — frontend changes now
  require a Node build step; `static/` becomes generated output rather than source.

## Capabilities

### New Capabilities

- `frontend-shell`: the frontend application shell — Vite + Svelte + TS toolchain, the
  feature-namespace source layout and no-cross-feature-imports rule, shell composition of features,
  build output served by FastAPI, and the dev-proxy workflow. The frontend counterpart of `app-shell`.
- `frontend-timeseries`: the timeseries dashboard UI — map with per-source markers and coincident-point
  clustering, source/category/status/jurisdiction/search/closed filters, incident table, detail panel
  with observation track, and live WebSocket diff application. The frontend counterpart of `timeseries`.

### Modified Capabilities

<!-- none — this change consumes the existing APIs exactly as specified; no backend requirement changes -->

## Impact

- **New:** `frontend/` (Svelte + TS source, `package.json`, `vite.config.ts`, `tsconfig.json`).
- **Replaced:** `static/app.js`, `static/index.html`, `static/style.css` are deleted from the repo;
  `static/` is added to `.gitignore` and produced by the build.
- **Modified:** `Dockerfile` (multi-stage Node → Python), `.gitignore`, `CLAUDE.md` (frontend stack,
  commands, and the "no build step" rationale), `README.md` if it describes the frontend.
- **Unchanged:** all backend code (`app/`), the API contract, the DB, `docker-compose.yml`
  (build context still `.`), and `main.py`'s static mount.
- **Dependencies added:** Node 22 (build-time only), `svelte@5`, `vite`, `typescript`, `leaflet`,
  `leaflet.markercluster`, `@types/leaflet`, `@types/leaflet.markercluster`.
