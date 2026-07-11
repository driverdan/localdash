## 1. Backend routers

- [x] 1.1 Create `app/api/timeseries.py` with an `APIRouter` holding the entities collection (`GET /entities` with `active`/`source`/`category`/`bbox`/`closed_within` filters, default `active=true`), entity snapshot (`GET /entities/{id}`, no embedded track), and track subresource (`GET /entities/{id}/track`), porting the query logic and `_bbox_filter` from `routes.py`
- [x] 1.2 Move `GET /observations`, `GET /sources`, `POST /sources/{key}/refresh`, and the WebSocket (as `/ws`) into the timeseries router unchanged in shape
- [x] 1.3 Create the root router (e.g., `app/api/root.py`) holding `GET /config`
- [x] 1.4 Update `app/main.py` to mount the timeseries router at `/api/v1/timeseries` and the root router at `/api/v1`, keeping the static mount last; delete `app/api/routes.py`

## 2. Frontend

- [x] 2.1 Update `static/app.js` URLs: `/api/v1/config`, `/api/v1/timeseries/entities?source=...` (replacing `/api/active`, translating `include_closed`/`closed_within_minutes` usage to `closed_within`), and the WebSocket path `/api/v1/timeseries/ws`
- [x] 2.2 Split the entity popup fetch into snapshot (`/entities/{id}`) + track (`/entities/{id}/track`) calls and merge for rendering

## 3. Tests

- [x] 3.1 Add offline route-shape tests (httpx `ASGITransport`): old flat routes 404, malformed `bbox` 400, `limit` > 50000 rejected, unknown-source refresh 404, `/api/v1/config` returns tile fields
- [x] 3.2 Add DB-backed route tests (same auto-skip pattern as `test_ingest_full_lifecycle`): entities default active-only, `closed_within` includes recently closed with `active:false`/`status:"Closed"`, snapshot has no `track` key, track subresource ordered oldest-first, unknown entity 404s

## 4. Docs & verification

- [x] 4.1 Update `CLAUDE.md` (API/frontend conventions and route references) to the `/api/v1/<feature>/` structure
- [x] 4.2 Run `pytest`, then `docker compose up --build` and verify the dashboard: map loads entities, popup shows detail + track, WebSocket diffs apply live
