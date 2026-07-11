## Why

LocalDash is growing from a single-purpose 911 map into a multi-feature data aggregation tool for the Chattanooga area, with upcoming features that are not time-series data and need a UI that is not a map. Today's API is flat (`/api/active`, `/api/observations`, ...) and verb-ish, so there is no route space or spec boundary for unrelated features to slot into. Breaking the routes is essentially free right now — the bundled frontend is the only consumer — and gets more expensive with every feature added.

## What Changes

- **BREAKING**: All API routes move under a versioned, feature-namespaced prefix: `/api/v1/timeseries/...` for everything time-series, `/api/v1/config` for global app bootstrap. Old flat routes are removed (no redirects).
- **BREAKING**: `GET /api/active` is re-modeled as `GET /api/v1/timeseries/entities` — entities become the resource; `active`, `source`, `category`, `bbox`, `closed_within` become filters on the collection. Default preserves today's semantics (`active=true`).
- **BREAKING**: The observation track is split out of entity detail: `GET /api/v1/timeseries/entities/{id}` returns the snapshot only; `GET /api/v1/timeseries/entities/{id}/track` returns the history.
- **BREAKING**: The WebSocket moves to `/api/v1/timeseries/ws`.
- `GET /observations`, `GET /sources`, and `POST /sources/{key}/refresh` keep their shapes and move into the `timeseries` namespace (sources are time-series machinery; future features won't share them).
- Code layout mirrors the route namespace: `app/api/routes.py` splits into a `timeseries` router and a root (app-level) router, composed in `main.py`. Adding a future feature becomes "new router module + one `include_router` line".
- The bundled frontend (`static/app.js`) is updated to the new routes (four URL references; entity popup becomes two calls).
- Route-level API tests are added (the suite currently has none).

## Capabilities

### New Capabilities
- `timeseries`: Time-series geolocation data over collected sources — the entities collection (current state), per-entity observation tracks, windowed observation queries, source registry/telemetry, manual refresh, and the live-diff WebSocket. This spec captures current behavior under the new RESTful route shapes.
- `app-shell`: Global, feature-agnostic API surface — versioned `/api/v1` prefix, the `/config` bootstrap endpoint, and the convention that each feature owns a namespace under `/api/v1/<feature>/`.

### Modified Capabilities

(none — `openspec/specs/` is empty; these are the project's first capability specs)

## Impact

- **Code**: `app/api/routes.py` (split), `app/main.py` (router composition + prefix), `static/app.js` (4 URL strings, popup fetch split), `CLAUDE.md` (API conventions section).
- **Not touched**: `models.py`, `ingest.py`, `scheduler.py`, `collectors/`, DB schema/migrations — the backend internals are already source-agnostic.
- **Consumers**: only the bundled frontend; it ships in the same repo and is updated in the same change. No external clients, so the breaking route changes carry no migration burden.
- **Tests**: existing tests reference no API paths and keep passing; new route-level tests are added for the v1 surface.
