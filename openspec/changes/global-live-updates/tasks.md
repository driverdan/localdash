## 1. Backend: global bus

- [x] 1.1 Generalize `ConnectionManager` in `app/ws.py`: drop the per-source subscription map (plain socket set + lock), broadcast every message to every client, keep dead-socket cleanup
- [x] 1.2 Add `topic: "timeseries"` to `Diff.to_message()` in `app/schemas.py`, and add a ping helper (broadcast `{topic, type: "updated"}`) to `app/ws.py`
- [x] 1.3 Add the `/api/v1/ws` WebSocket route to `app/api/root.py` (accept, hold, disconnect cleanup — mirror the old handler); remove the `/ws` route and its `source` query param from `app/api/timeseries.py`
- [x] 1.4 Update/extend backend tests covering the endpoint move and envelope (grep `tests/` for the old `/api/v1/timeseries/ws` path and `to_message` expectations)

## 2. Backend: update signals

- [x] 2.1 Broadcast a `news` ping at the end of every completed cycle in `app/news/refresh.py::refresh()` (inside the lock's success path, so scheduled and manual refreshes both signal; failures raise before the ping)
- [x] 2.2 Broadcast an `events` ping in `app/events/refresh.py::refresh()` when any of `stats["created"]`, `stats["merged"]`, `stats["resolved"]`, `stats["reconciled"]` is nonzero
- [x] 2.3 Add a scheduled weather job in `app/scheduler.py` (gated by `weather_enabled`, interval `weather_cache_minutes`): call the weather service, compare the shaped payload to the previous one, ping `weather` on change; log-and-skip on failure
- [x] 2.4 Add tests for signal emission: news ping every cycle, events ping only on nonzero counts, weather ping only on payload change

## 3. Frontend: singleton bus

- [x] 3.1 Add `frontend/src/lib/live.svelte.ts`: one connection to `/api/v1/ws` via `connectWebSocket`, `subscribe(topic, handler)` with disposers, reactive `connecting | live | disconnected` state, and `onReconnect(handler)` that skips the boot-time first connect
- [x] 3.2 Start the connection from the app shell and switch the header status indicator to the bus connection state, shown on all routes (drop the map-only gating and the timeseries-owned `connectionState` export)

## 4. Frontend: feature wiring

- [x] 4.1 Timeseries: rewrite `features/timeseries/live.ts` `connectLive()` as a mount-scoped bus subscription to `timeseries` (same diff application) plus an `onReconnect` handler that re-runs `loadActive()`; drop `ts.connection`
- [x] 4.2 News: export a `registerLive()` that permanently subscribes to `news` pings and reconnects, refetching stories+sources with current `hours`; delete the 5-minute `setInterval` in `NewsFeed.svelte`
- [x] 4.3 Events: export a `registerLive()` that permanently subscribes to `events` pings and reconnects, re-running `loadItems()` with active filters; delete the 5-minute `setInterval` in `EventsPage.svelte`
- [x] 4.4 Home: export a `registerLive()` subscribing the stories digest to `news`, events digest to `events`, and weather strip to `weather` (plus reconnect); call all `registerLive()`s once from `App.svelte`
- [x] 4.5 Update frontend spec-adjacent docs/comments that reference `/api/v1/timeseries/ws` or interval polling

## 5. Verification

- [x] 5.1 Backend tests pass (`pytest`); frontend checks pass (`svelte-check`, build)
- [x] 5.2 Rebuild and run via `sg docker -c 'docker compose up --build'`; confirm one `/api/v1/ws` connection in devtools, live map diffs still apply, and a debug-panel news/events refresh pings and refreshes the open page without reload
- [x] 5.3 Verify reconnect behavior: restart the backend container with the page open — indicator goes disconnected, reconnects, and features refetch
