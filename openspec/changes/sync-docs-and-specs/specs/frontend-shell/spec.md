## MODIFIED Requirements

### Requirement: Feature-namespaced frontend source layout
The frontend SHALL be a Svelte 5 + TypeScript application under `frontend/`, organized in feature
namespaces mirroring the API: each feature owns `frontend/src/features/<feature>/` (matching its API
namespace `/api/v1/<feature>/`), and feature-agnostic shell code lives in `frontend/src/lib/`.
Feature code SHALL NOT import another feature's internals: a cross-feature import, like the app
shell's (`App.svelte`) composition of features, SHALL resolve only to that feature's `index.ts`
public surface (e.g. the home feature reusing the news card component). `lib/` SHALL NOT import
from any feature. Adding a frontend feature MUST NOT require modifying another feature's code.

#### Scenario: Features are isolated namespaces
- **WHEN** the source under `frontend/src/features/<feature>/` is inspected
- **THEN** its imports resolve only to that feature's own files, another feature's `index.ts`
  public surface, `frontend/src/lib/`, or third-party packages — never to files inside another
  feature's namespace

#### Scenario: Shell composes features per route
- **WHEN** a new feature folder is added under `frontend/src/features/`
- **THEN** wiring it into the UI requires only shell-level additions — importing its `index.ts`
  surface in `App.svelte`, adding its route entry and nav link, importing its stylesheet in
  `main.ts`, and (for a live feature) calling its live-registration function — with no changes
  inside `frontend/src/lib/` or other features

### Requirement: Frontend dev server proxies the API
Local frontend development SHALL use the Vite dev server with a proxy forwarding `/api` requests —
including the WebSocket upgrade for the shared live-update bus at `/api/v1/ws` — to the locally running backend, so the
backend requires no CORS or configuration changes for development.

#### Scenario: Dev server round-trips REST and WebSocket
- **WHEN** the backend runs on `:8000` and `npm run dev` serves the frontend
- **THEN** the app loaded from the Vite dev server successfully fetches `/api/v1/...` endpoints and
  holds a live `/api/v1/ws` connection through the proxy

### Requirement: Client-side path routing
The shell SHALL provide a minimal path router in `frontend/src/lib/` (no external routing
dependency): it tracks the current path as reactive state, navigates via the History API
(`pushState` plus a `popstate` listener, so back/forward work), and lets `App.svelte` map paths to
features. The route table SHALL be: `/` renders the home feature, `/news` renders the news
feature, `/map` renders the timeseries feature, and `/events` renders the events feature. The
shell SHALL render a persistent navigation header linking the routes. Unknown paths SHALL show a
not-found message linking back to the home page. The header SHALL show the shared live-update
bus's connection indicator on every route, since every feature receives live updates.

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

#### Scenario: Connection indicator shows on every route
- **WHEN** any route (`/`, `/news`, `/map`, or `/events`) is active
- **THEN** the header shows the live-update bus connection state (live, connecting, or
  disconnected)
