# frontend-shell — delta

## ADDED Requirements

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

#### Scenario: Shell composes features at one mount point
- **WHEN** a new feature folder is added under `frontend/src/features/`
- **THEN** wiring it into the UI requires only importing its `index.ts` surface in `App.svelte`, with
  no changes inside `frontend/src/lib/` or other features

### Requirement: Build output served by the existing static mount
The frontend SHALL be built by Vite into `static/` as a self-contained bundle (Leaflet and all other
dependencies bundled from npm, no CDN/runtime network dependencies for assets), and FastAPI SHALL
serve it through its existing `/` static mount without backend code changes. `static/` SHALL be a
gitignored build artifact, not checked-in source.

#### Scenario: Built bundle served by FastAPI
- **WHEN** `vite build` has run and the app starts
- **THEN** `GET /` serves the built `index.html` from `static/` and all referenced assets load from
  the same origin, with no requests to CDN hosts

#### Scenario: API routes still win over static files
- **WHEN** a client requests any `/api/...` path
- **THEN** the API handles it; the static mount serves only non-`/api` paths (unchanged from before)

### Requirement: Node is confined to build time
The Docker image SHALL be produced by a multi-stage build in which a Node stage builds the frontend
and the Python runtime stage only copies the built `static/` output. The runtime image and the
running application SHALL NOT require Node.

#### Scenario: Fresh image contains a fresh build
- **WHEN** `docker compose up --build` runs
- **THEN** the image's `static/` content is built from the current `frontend/` source during the
  image build, and the final image contains no Node toolchain

### Requirement: Frontend dev server proxies the API
Local frontend development SHALL use the Vite dev server with a proxy forwarding `/api` requests —
including the WebSocket upgrade for `/api/v1/timeseries/ws` — to the locally running backend, so the
backend requires no CORS or configuration changes for development.

#### Scenario: Dev server round-trips REST and WebSocket
- **WHEN** the backend runs on `:8000` and `npm run dev` serves the frontend
- **THEN** the app loaded from the Vite dev server successfully fetches `/api/v1/...` endpoints and
  holds a live `/api/v1/timeseries/ws` connection through the proxy

### Requirement: TypeScript checking passes
The frontend SHALL compile under TypeScript with `svelte-check` (strict mode) reporting no errors,
and the shared API data contracts (GeoJSON feature shape, bootstrap config) SHALL be expressed as
types in `frontend/src/lib/`.

#### Scenario: Type check gate
- **WHEN** `npm run check` (svelte-check) runs in `frontend/`
- **THEN** it exits successfully with zero type errors
