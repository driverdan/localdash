## Context

All seven endpoints live in one flat router (`app/api/routes.py`) mounted at `/api`. Route names are query-shaped rather than resource-shaped (`/active`), entity detail embeds the full observation track, and there is no namespace separating the time-series feature from the API surface future (non-map, non-time-series) features will need. The only consumer is the bundled frontend (`static/app.js`, four URL references), so breaking routes now costs nothing; `openspec/specs/` is empty, so this change also establishes the first capability specs.

## Goals / Non-Goals

**Goals:**
- Every time-series endpoint lives under `/api/v1/timeseries/`; future features get sibling namespaces under `/api/v1/<feature>/`.
- Resource-oriented (RESTful) route shapes: collections + filters, subresources for history, no query-named routes.
- Code layout mirrors the route map so adding a feature is a new router module + one `include_router` line.
- Frontend keeps working identically after the move.

**Non-Goals:**
- No changes to the data model, ingest pipeline, scheduler, collectors, or DB schema — internals are already source-agnostic.
- No vertical-slice restructure (`app/features/timeseries/` owning ingest/models). Revisit if a second feature actually needs it.
- No pagination on entities or track (noted as future non-breaking additions), no auth, no response-shape redesign beyond the split described below — bodies stay GeoJSON/JSON as today.
- No back-compat redirects from old routes.

## Decisions

- **Version prefix `/api/v1` now.** We are already breaking every route; adding the version segment later would be a second break. Composed centrally in `main.py` so routers don't hardcode it. Alternative (no versioning) rejected: an area data-aggregation API plausibly grows consumers beyond the bundled frontend.
- **`/active` → `GET /timeseries/entities`.** Entities are the resource; `active`, `source`, `category`, `bbox`, `closed_within` are collection filters. Default is `active=true`, preserving today's semantics — entities accumulate forever (closure only flips `is_active`), so an unfiltered collection would be unbounded. The old `include_closed=true&closed_within_minutes=N` pair becomes a single `closed_within=N` filter (minutes): passing it includes entities closed within that window alongside active ones, exactly the old behavior. `active=false` returns only inactive entities.
- **Track as a subresource.** `GET /entities/{id}` returns the snapshot only; `GET /entities/{id}/track` returns the ordered observation history. Cleaner resource model, and the subresource can gain `start`/`end`/limit params non-breakingly when tracks grow. Alternative (keep embedded) rejected: detail payloads grow unboundedly and can't be filtered. Cost: the frontend popup makes two calls; acceptable on a LAN dashboard.
- **Sources live inside the timeseries namespace** (`/timeseries/sources`, `POST /timeseries/sources/{key}/refresh`). Sources/collectors are time-series machinery; upcoming features explicitly won't share them. `refresh` stays an action endpoint — pragmatic REST, not worth remodeling as a runs resource.
- **WebSocket at `/api/v1/timeseries/ws`.** The live diff stream is a timeseries concern; versioning applies to its message shape too.
- **`/api/v1/config` stays global** (app-shell), serving whatever views the UI grows. Feature-specific config, if ever needed, would live under the feature's namespace.
- **Router composition:** `app/api/timeseries.py` exports an `APIRouter` with all timeseries routes (paths relative to its namespace); a root router holds `/config`. `main.py` mounts: `app.include_router(timeseries.router, prefix="/api/v1/timeseries")`, `app.include_router(root.router, prefix="/api/v1")`, static mount last so `/api` always wins. `app/api/routes.py` is deleted, not kept as a shim.

## Risks / Trade-offs

- [Old routes return 404 the moment the server restarts with a stale cached frontend] → frontend and API ship in the same image/repo and are updated in the same commit; no deployment skew possible beyond a hard browser refresh.
- [Popup latency doubles (two fetches: snapshot + track)] → negligible at this scale; if it ever matters, fire the two fetches concurrently in `app.js`.
- [Renaming `include_closed`/`closed_within_minutes` to `closed_within` silently changes API vocabulary] → captured in the spec; no external consumers exist to confuse.
- [Route-level tests are new territory — the suite currently exercises no HTTP layer] → use `httpx.ASGITransport` against the FastAPI app with the DB-backed pattern already established by `test_ingest_full_lifecycle` (auto-skip without a reachable Postgres); pure route-shape tests (404s, param validation) can run offline.

## Migration Plan

1. Add the new routers and mounts (old routes deleted in the same commit — no coexistence window).
2. Update `static/app.js` URLs and split the popup fetch.
3. Update `CLAUDE.md` API conventions.
4. `docker compose up --build`; verify map loads, popups show tracks, WebSocket diffs apply.

Rollback: single revert — no schema or data migration is involved.

## Open Questions

(none — boundary decisions were settled during exploration: full resource shapes, v1 prefix, track subresource, sources under timeseries, default `active=true`)
