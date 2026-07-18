# frontend-shell Specification

## Purpose

The frontend application shell: the Svelte 5 + TypeScript + Vite toolchain, the feature-namespace
source layout mirroring the API (`frontend/src/features/<feature>/` ↔ `/api/v1/<feature>/`) with its
import rules, the build/serve contract (Vite builds into `static/`, FastAPI serves it unchanged), and
the dev-proxy workflow. The frontend counterpart of the `app-shell` spec — the conventions that let
new, unrelated frontend features be added beside `timeseries` without touching it.
## Requirements
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

### Requirement: Client-side path routing
The shell SHALL provide a minimal path router in `frontend/src/lib/` (no external routing
dependency): it tracks the current path as reactive state, navigates via the History API
(`pushState` plus a `popstate` listener, so back/forward work), and lets `App.svelte` map paths to
features. The route table SHALL be: `/` renders the home feature, `/news` renders the news
feature, `/map` renders the timeseries feature, and `/events` renders the events feature. The
shell SHALL render a persistent navigation header linking the routes. Unknown paths SHALL show a
not-found message linking back to the home page. Feature-specific UI (such as the timeseries
connection indicator) SHALL appear only on that feature's route.

#### Scenario: Root renders the home feature
- **WHEN** the user opens `/`
- **THEN** the home landing page renders, not the news feed

#### Scenario: Nav switches features without a reload
- **WHEN** the user clicks "News" in the nav from the home page
- **THEN** the URL becomes `/news` and the news feed renders without a full page load

#### Scenario: Events route renders the events feature
- **WHEN** the user clicks "Events" in the nav
- **THEN** the URL becomes `/events` and the events feature renders without a full page load

#### Scenario: Browser history works
- **WHEN** the user navigates `/` → `/map` and presses the browser back button
- **THEN** the home feature renders at `/` without a full page load

#### Scenario: Unknown path links home
- **WHEN** the user opens an unrecognized path such as `/nope`
- **THEN** a not-found message renders with a link that navigates to `/`

#### Scenario: Timeseries indicator is scoped to its route
- **WHEN** the home or news route is active
- **THEN** the timeseries WebSocket connection indicator is not shown

### Requirement: Shell hosts theming
The application shell SHALL host the theme system's user-facing and bootstrap surfaces: a
discoverable theme switcher rendered in the header (the always-present surface across all routes),
and a synchronous inline bootstrap script in `index.html` that applies the saved theme to the
document root before the app bundle loads. The switcher SHALL be feature-agnostic shell code
(`frontend/src/lib/` + `App.svelte`/header), consistent with the shell's ownership of nav and the
status bar.

#### Scenario: Switcher is present on every route
- **WHEN** the user is on any route (map, news, or events)
- **THEN** the header shows the theme switcher, and changing it re-styles the current page
  immediately

#### Scenario: Bootstrap runs before the app bundle
- **WHEN** `index.html` loads
- **THEN** the inline theme bootstrap script runs and sets the document-root theme before the app
  bundle initializes, so the shell and first route paint in the saved theme

### Requirement: Site footer with open-source attribution
The shell SHALL provide a shared site footer component (in `frontend/src/lib/`) containing a
single link with the text "100% Open Source" pointing at
`https://github.com/driverdan/localdash`, opening in a new tab so in-app state (including the
live WebSocket connection) is preserved. The footer SHALL be rendered in the flow of the
scrollable content — as the last element inside the route's scroll region — on the home, news,
and events routes, so it appears after the content rather than as a fixed always-visible strip.
The viewport-locked map route SHALL NOT render the site footer. The footer SHALL be styled via
the global stylesheet using existing design tokens only, so all themes inherit it without
per-theme rules.

#### Scenario: Footer reached by scrolling content routes
- **WHEN** the user scrolls to the bottom of the content on the home, news, or events route
- **THEN** a site footer appears after the route's content containing a "100% Open Source" link
  to `https://github.com/driverdan/localdash`

#### Scenario: Footer is not fixed
- **WHEN** a content route's content overflows its scroll region and the user has not scrolled
  to the bottom
- **THEN** the site footer is not visible on screen (it flows after the content rather than
  being pinned to the viewport)

#### Scenario: Link preserves the running app
- **WHEN** the user activates the "100% Open Source" link
- **THEN** the repository page opens in a new tab and the dashboard keeps running (the live
  WebSocket connection is not torn down)

#### Scenario: Map route has no footer
- **WHEN** the user visits `/map`
- **THEN** no site footer is rendered

### Requirement: Site name is displayed from runtime configuration

The shell SHALL display the site name from the runtime-configured value rather than any hardcoded
string, consistently across the surfaces where the name appears. The built `index.html` SHALL carry
placeholder tokens (for the `<title>` and for a synchronous `window.__SITE_NAME__` assignment) that
the backend replaces at serve time; the header `<h1>` SHALL render the value read synchronously from
`window.__SITE_NAME__`, so it is correct at first paint with no additional network request and no
flash of a placeholder value. The previously hardcoded `Chattanooga ` prefix and ` (beta)` suffix
SHALL NOT be applied by the shell — the displayed name is exactly the configured value.

#### Scenario: Header shows the configured name

- **WHEN** the app loads and the backend has injected `window.__SITE_NAME__` as `Acme Dashboard`
- **THEN** the header `<h1>` renders `Acme Dashboard`, matching the browser tab title, with no
  additional fetch for the name

#### Scenario: No hardcoded qualifiers

- **WHEN** the configured site name is `LocalDash`
- **THEN** the header renders exactly `LocalDash` (not `Chattanooga LocalDash (beta)`)

#### Scenario: Placeholders present in built output for injection

- **WHEN** `vite build` has produced `static/index.html`
- **THEN** the built file contains the placeholder tokens the backend substitutes for the title and
  the `window.__SITE_NAME__` global, so serve-time injection has a defined target

