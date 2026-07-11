# Design — migrate-frontend-svelte

## Context

The frontend is one vanilla-JS file (`static/app.js`, 451 lines) plus `index.html` and `style.css`,
with Leaflet and markercluster loaded from a CDN and no build step. FastAPI mounts `static/` at `/`
(`app/main.py:55`, `NoCacheStaticFiles`, mounted last so `/api` wins). The app already has a clean
implicit structure: per-source display config (`SOURCES`), client state (`features`/`markers` Maps,
`filters`, `selectedSources`), manual render functions (`renderMarker`, `renderTable`,
`renderFilterOptions`), REST loading, and a reconnecting WebSocket applying live diffs.

The backend is feature-namespaced (`/api/v1/timeseries/`, app-shell endpoints at `/api/v1`); adding a
backend feature is one router module + one `include_router` line. The frontend has no equivalent
seam — everything lives in one file, and the state↔DOM synchronization plumbing grows with every
control added.

## Goals / Non-Goals

**Goals:**
- Svelte 5 + TypeScript frontend built with plain Vite, organized in feature namespaces mirroring the
  API: `src/features/<feature>/` per feature, `src/lib/` for the feature-agnostic shell.
- A straight port: pixel-for-pixel, behavior-for-behavior equivalent of today's UI.
- Zero backend changes; `static/` remains the serving contract.
- A contained toolchain: Node is needed to *build* the frontend, never to *run* the app.

**Non-Goals:**
- No new UI features, no visual redesign, no behavior changes (they come after, as their own changes).
- No SvelteKit, no SSR, no client-side router — one screen, mounted by a static bundle.
- No shared-map abstraction: the Leaflet map belongs to the timeseries feature until a second feature
  actually needs it. Designing a layer-registration contract with one consumer is premature.
- No frontend test framework in this change (nothing exists today; adding one is a separate decision).

## Decisions

### D1: Plain Vite + `@sveltejs/vite-plugin-svelte`, not SvelteKit
FastAPI is the server; the frontend is a static SPA bundle it mounts. SvelteKit's routing, adapters,
and `+page` conventions solve problems this app doesn't have and would put a second server framework
in the repo. If a multi-view UI emerges later, a client-side router (or SvelteKit) can be adopted then.

### D2: Feature-namespace source layout, mirroring the API

```
frontend/
  package.json  vite.config.ts  tsconfig.json  index.html
  src/
    main.ts                     # mounts App
    App.svelte                  # app shell: header, status bar, layout; mounts features
    lib/                        # feature-agnostic (mirrors /api/v1 app-shell)
      api.ts                    #   fetch base + GET /api/v1/config + GeoJSON types
      ws.ts                     #   reconnecting-WebSocket helper (retry w/ 3s backoff)
      format.ts                 #   esc / cap / fmt utilities
    features/
      timeseries/               # mirrors /api/v1/timeseries/*
        index.ts                #   public surface: the component(s) the shell mounts
        types.ts                #   TrackedFeature, TrackPoint, SourceConfig
        sources.ts              #   hc911 / tdot / epb display config + FALLBACK
        api.ts                  #   entities / entity / track fetches
        live.ts                 #   /timeseries/ws subscription -> store mutations
        state.svelte.ts         #   runes store: features, filters, selectedSources,
                                #   $derived visibleFeatures / categories / dropdown values
        components/
          MapView.svelte        #   imperative Leaflet + cluster + track layer + legend
          FilterPanel.svelte
          IncidentTable.svelte
          DetailPanel.svelte
```

**Import rules** (the frontend analog of "ingest never knows about source specifics"):
- `features/*` may import from `lib/` and from within themselves — never from another feature.
- `App.svelte` imports only each feature's `index.ts` and `lib/`.
- `lib/` imports from no feature.

Adding a frontend feature = new `features/<name>/` folder + one mount in `App.svelte`, mirroring
"new router module + one `include_router` line."

### D3: Vite builds into `static/`; FastAPI is untouched
`vite.config.ts` sets `build.outDir: ../static` (`emptyOutDir: true`). `static/` moves from
checked-in source to gitignored build artifact; `app/main.py`'s mount and the `NoCacheStaticFiles`
behavior stay exactly as they are. Alternative considered — serving from `frontend/dist` and changing
`STATIC_DIR` — rejected: it touches backend code for no benefit and breaks the Dockerfile's existing
`COPY static ./static`.

### D4: Multi-stage Docker build; Node is build-time only
```
FROM node:22-slim AS frontend   # COPY frontend/, npm ci, npm run build  -> /static
FROM python:3.12-slim           # existing stage, but COPY --from=frontend /static ./static
```
`docker-compose.yml` is unchanged (build context is still `.`). The runtime image gains no Node.

**Local dev:** `vite dev` on :5173 with `server.proxy` forwarding `/api` (and `ws: true` for
`/api/v1/timeseries/ws`) to `http://localhost:8000`. Backend workflow (`uvicorn --reload`) is
unchanged; a developer touching only Python never runs Node — but then sees whatever `static/` build
is present, so `npm run build` is part of "run the full stack from source."

### D5: State is a runes module; rendering is derived, not orchestrated
`state.svelte.ts` holds `$state` for the raw inputs (`features: Map`, `filters`, `selectedSources`)
and `$derived` for everything currently maintained by hand: the filtered+sorted visible list
(`passesFilters` + the `last_seen_at` sort), the category set across selected sources, and the
status/jurisdiction dropdown values (including the "drop a selected value that no longer exists"
reconciliation, which becomes a `$derived` + reset effect instead of `reconcileSelect`). The
`refreshAll`/`renderFilterOptions`/`renderTable` call-graph is deleted, not ported — that plumbing is
the framework's job now. Svelte 5's `SvelteMap`/`SvelteSet` (from `svelte/reactivity`) are used so
Map/Set mutations are tracked.

### D6: MapView keeps Leaflet fully imperative
No marker components, no Svelte-Leaflet wrapper library. `MapView.svelte` owns `L.map`, the tile
layer (from `/api/v1/config`), the `markerClusterGroup({ maxClusterRadius: 1 })`, the EPB legend
control, the track `layerGroup`, and a private `markers: Map<id, L.Marker>`. One `$effect` reconciles
markers against the derived visible set exactly the way `renderMarker`/`removeFeature` do today
(remove-then-re-add on change; divIcon pins and per-source sized dots preserved verbatim). This keeps
the 100s-of-live-markers path out of the component re-render cycle and preserves current behavior.

### D7: Leaflet from npm, typed
`leaflet` + `leaflet.markercluster` and their `@types/*` packages replace the four unpkg CDN tags;
CSS imported from the packages so the bundle is self-contained. Pins the versions and removes the
runtime CDN dependency.

### D8: Typed boundary in `types.ts`
`TrackedFeature` types the GeoJSON feature contract the API guarantees (authoritative properties:
`id`, `source`, `external_id`, `category`, `label`, `last_seen_at`, `active`, `status`) with
`Record<string, unknown>` for source-specific properties; `SourceConfig` types the per-source display
config (`title`/`location`/`jurisdiction`/`detail` accessors, colors, optional `round`/`markerColor`/
`markerSize`). `sources.ts` stays the single place source-specific knowledge lives, now compiler-checked.

## Risks / Trade-offs

- **[Repo loses toolchain-freeness]** → Deliberate and accepted in the proposal; contained by D3/D4
  (Node never required at runtime; backend-only devs can keep a prebuilt `static/`). CLAUDE.md updated
  so the old "no build step on purpose" rationale doesn't mislead.
- **[Behavior drift during the port]** → The port is mechanical and reviewed against the old file
  side-by-side; both UIs speak to the same backend, so they can be compared live. Filter semantics,
  popup/detail content, and marker styling are pinned by the `frontend-timeseries` spec scenarios.
- **[`static/` is gitignored — a stale build can be served]** → Docker always builds fresh (D4);
  documented for local dev. `emptyOutDir` prevents mixed old/new artifacts.
- **[markercluster's community types lag]** → Minor; escape-hatch casts are acceptable at the two
  call sites that need them.
- **[Svelte 5 runes are newer than Svelte 4 idioms]** → Runes are the current stable API and the
  right target for new code; no legacy Svelte code exists to conflict.

## Migration Plan

1. Land `frontend/` + Dockerfile change + gitignore/doc updates in one PR (per repo git workflow:
   branch → PR).
2. Old files are deleted in the same PR — `static/` cannot hold both, since Vite owns the directory.
3. Rollback = revert the PR; the old frontend is fully restored from git, backend untouched.

## Open Questions

None blocking. (Deferred by design: shared-map extraction, client-side routing, frontend tests.)
