# Tasks — migrate-frontend-svelte

## 1. Scaffold the toolchain

- [x] 1.1 Create `frontend/` with `package.json` (svelte@5, vite, `@sveltejs/vite-plugin-svelte`,
      typescript, svelte-check, leaflet, leaflet.markercluster, `@types/leaflet`,
      `@types/leaflet.markercluster`), `tsconfig.json` (strict), and `frontend/index.html` (port of
      the current page shell: header, sidebar layout containers, map div, detail panel)
- [x] 1.2 Write `vite.config.ts`: svelte plugin, `build.outDir: "../static"` + `emptyOutDir: true`,
      and `server.proxy` forwarding `/api` (with `ws: true`) to `http://localhost:8000`
- [x] 1.3 Add npm scripts (`dev`, `build`, `check`) and verify an empty Svelte app builds into
      `static/` and is served by FastAPI at `/`
- [x] 1.4 Add `static/` to `.gitignore` (keep the old files in git until task 6.1 deletes them)

## 2. Shell + shared lib

- [x] 2.1 Port utilities to `src/lib/format.ts` (`esc` only if still needed post-Svelte, `cap`,
      `fmt`) and define shared API types + fetch helpers in `src/lib/api.ts` (GeoJSON
      FeatureCollection types, `GET /api/v1/config`)
- [x] 2.2 Write `src/lib/ws.ts`: reconnecting-WebSocket helper (connect, onmessage callback,
      3s retry on close, connection-state callback), feature-agnostic
- [x] 2.3 Write `App.svelte` (header, live/disconnected status bar, layout) + `src/main.ts` mount;
      the shell imports the timeseries feature only via `features/timeseries/index.ts`

## 3. Timeseries feature — state and data

- [x] 3.1 Write `features/timeseries/types.ts` (`TrackedFeature`, `TrackPoint`, `SourceConfig`) and
      port `SOURCES`/`FALLBACK`/`cfgFor` + EPB marker helpers to `sources.ts`, fully typed
- [x] 3.2 Write `state.svelte.ts`: `$state` for `features` (SvelteMap), `filters`, `selectedSources`
      (SvelteSet); `$derived` for visible features (port `passesFilters` + table sort), selected
      categories, category colors, and status/jurisdiction dropdown options with stale-selection
      reset (replaces `refreshAll`/`renderFilterOptions`/`reconcileSelect`)
- [x] 3.3 Write `api.ts` (fetch entities per source with optional `closed_within`, entity snapshot,
      entity track) and `live.ts` (subscribe via `lib/ws.ts`, apply diffs: upsert new/updated, close
      ids per show-closed mode, ignore unselected sources) with load/`toggleSource` actions mutating
      the store

## 4. Timeseries feature — components

- [x] 4.1 Write `MapView.svelte`: imperative Leaflet init from `/api/v1/config`, cluster group
      (`maxClusterRadius: 1`), EPB legend control, divIcon builders (pin + sized round dot, closed
      styling), and one `$effect` reconciling a private `markers` Map against the derived visible
      set; popups + marker click → detail
- [x] 4.2 Write `FilterPanel.svelte`: source checkboxes, category checkboxes with color dots,
      status/jurisdiction selects, search input, show-closed toggle + closed-window select (refetch
      on change), all bound to the store
- [x] 4.3 Write `IncidentTable.svelte`: visible entities sorted by `last_seen_at` desc, count,
      closed-row styling + badge, row click → detail + `map.flyTo`
- [x] 4.4 Write `DetailPanel.svelte`: concurrent snapshot+track fetch, source-specific detail rows
      (empty values omitted), history list newest-first; track drawing (dashed polyline + circle
      markers) on the map, cleared on close
- [x] 4.5 Port `style.css` into the app (global stylesheet or component styles), preserving current
      look: marker pin/dot/closed styles, legend, table, badges, detail panel

## 5. Docker + docs

- [x] 5.1 Convert `Dockerfile` to multi-stage: `node:22-slim` stage runs `npm ci && npm run build`
      on `frontend/`; Python stage replaces `COPY static ./static` with `COPY --from=frontend`
- [x] 5.2 Update `CLAUDE.md` (frontend stack + rationale replacing the "no build step" note, feature
      -namespace convention and import rules, dev/build commands) and `README.md` if it mentions the
      frontend
- [x] 5.3 Add `frontend/node_modules/` to `.gitignore`

## 6. Cutover + verification

- [x] 6.1 Delete `static/app.js`, `static/index.html`, `static/style.css` from git (directory is now
      build output only)
- [x] 6.2 `npm run check` passes with zero errors; `npm run build` produces a working bundle
- [x] 6.3 Verify parity against the running backend (`docker compose up --build`): initial load, all
      marker styles + coincident clustering + legend, every filter incl. stale-dropdown reset,
      show-closed refetch, table sort + row click flyTo, detail panel + track draw/clear, live WS
      diffs incl. closed handling, and reconnect after killing the connection
- [x] 6.4 Verify the dev-proxy workflow: backend on :8000, `npm run dev`, REST + WebSocket both work
      through the Vite proxy
