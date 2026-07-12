## ADDED Requirements

### Requirement: Client-side path routing
The shell SHALL provide a minimal path router in `frontend/src/lib/` (no external routing
dependency): it tracks the current path as reactive state, navigates via the History API
(`pushState` plus a `popstate` listener, so back/forward work), and lets `App.svelte` map paths to
features. The route table SHALL be: `/` renders the news feature and `/map` renders the
timeseries feature. The shell SHALL render a persistent navigation header linking the routes.
Feature-specific UI (such as the timeseries connection indicator) SHALL appear only on that
feature's route.

#### Scenario: Nav switches features without a reload
- **WHEN** the user clicks "Map" in the nav from the news homepage
- **THEN** the URL becomes `/map` and the timeseries dashboard renders without a full page load

#### Scenario: Browser history works
- **WHEN** the user navigates `/` → `/map` and presses the browser back button
- **THEN** the news feature renders at `/` without a full page load

#### Scenario: Timeseries indicator is scoped to its route
- **WHEN** the news route is active
- **THEN** the timeseries WebSocket connection indicator is not shown

## MODIFIED Requirements

### Requirement: Feature-namespaced frontend source layout
The frontend SHALL be a Svelte 5 + TypeScript application under `frontend/`, organized in feature
namespaces mirroring the API: each feature owns `frontend/src/features/<feature>/` (matching its API
namespace `/api/v1/<feature>/`), and feature-agnostic shell code lives in `frontend/src/lib/`.
Feature code SHALL NOT import from another feature; the app shell (`App.svelte`) SHALL compose
features only through each feature's `index.ts` public surface; `lib/` SHALL NOT import from any
feature. Adding a frontend feature MUST NOT require modifying another feature's code.

#### Scenario: Features are isolated namespaces
- **WHEN** the source under `frontend/src/features/<feature>/` is inspected
- **THEN** its imports resolve only to that feature's own files, `frontend/src/lib/`, or third-party
  packages — never to another feature's namespace

#### Scenario: Shell composes features per route
- **WHEN** a new feature folder is added under `frontend/src/features/`
- **THEN** wiring it into the UI requires only importing its `index.ts` surface in `App.svelte` and
  adding one route entry, with no changes inside `frontend/src/lib/` or other features

### Requirement: Build output served by the existing static mount
The frontend SHALL be built by Vite into `static/` as a self-contained bundle (Leaflet and all other
dependencies bundled from npm, no CDN/runtime network dependencies for assets), and FastAPI SHALL
serve it through its `/` static mount (including the SPA fallback owned by `app-shell`). `static/`
SHALL be a gitignored build artifact, not checked-in source.

#### Scenario: Built bundle served by FastAPI
- **WHEN** `vite build` has run and the app starts
- **THEN** `GET /` serves the built `index.html` from `static/` and all referenced assets load from
  the same origin, with no requests to CDN hosts

#### Scenario: API routes still win over static files
- **WHEN** a client requests any `/api/...` path
- **THEN** the API handles it; the static mount serves only non-`/api` paths (unchanged from before)
