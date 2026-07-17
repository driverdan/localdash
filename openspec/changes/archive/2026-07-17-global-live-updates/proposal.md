## Why

Only the timeseries map updates live today; news, events, and the home page rely on blind client-side polling timers (or a single fetch on mount) that are unrelated to when the server actually refreshed, so new data appears late — or never, until a reload. One global WebSocket connection carrying updates for every feature makes the whole dashboard self-updating and removes the guess-timers.

## What Changes

- Add a single app-level WebSocket endpoint at `/api/v1/ws` carrying a topic envelope: timeseries keeps its full diff payloads (`topic: "timeseries"`), while news, events, and weather get lightweight invalidation pings (`topic: "<feature>", type: "updated"`) that tell the client to refetch through the REST endpoints it already uses (preserving server-side filtering).
- **BREAKING**: Remove the feature-scoped `/api/v1/timeseries/ws` endpoint and its per-source `source` query filter (the bundled frontend never used the filter; frontend and backend ship together).
- Backend refresh cycles emit change signals: the events refresh pings when anything was created/merged/updated, the news refresh pings after each completed cycle, and weather gains a scheduled proactive refresh job that pings when the shaped payload changes (its cache is currently only refreshed lazily on request, so it has no push moment today).
- Frontend gains a singleton connection + topic subscription bus in `lib/`; news, events, and home register permanent subscriptions from the app shell so their module-singleton stores stay fresh even while their route isn't visible (refetching on reconnect to recover missed pings), while timeseries keeps its mount-scoped subscription through the same bus (its dashboard already reloads active entities on every mount).
- Remove the 5-minute `setInterval` polling from the news and events pages; the home page digests and weather strip update via the same subscriptions.

## Capabilities

### New Capabilities

- `live-updates`: the backend global WebSocket bus — the `/api/v1/ws` endpoint, the topic envelope message contract (timeseries diffs as data, news/events/weather as invalidation pings), and the change-signal emission rules for each feature's refresh cycle.
- `frontend-live`: the frontend singleton WebSocket connection and topic subscription bus in `frontend/src/lib/`, including reconnection, refetch-on-reconnect, and permanent feature subscriptions registered from the app shell.

### Modified Capabilities

- `timeseries`: the "Live diff WebSocket" requirement changes — diffs are delivered over the global bus instead of `/api/v1/timeseries/ws`; the feature-scoped endpoint and per-source stream filter are removed.
- `frontend-timeseries`: "Live updates over WebSocket" changes to consume timeseries diffs via the shared subscription bus (connection indicator driven by shared connection state) instead of opening its own socket.
- `news`: the scheduled refresh requirement gains an update signal — each completed fetch+recluster cycle notifies the live-updates bus.
- `events`: the scheduled refresh requirement gains an update signal — a cycle that changed data (created/merged/images/geocoding backfill) notifies the live-updates bus.
- `weather`: caching gains a scheduled proactive refresh at the cache-TTL interval, emitting an update signal when the shaped payload changes.
- `frontend-news`: interval polling is replaced by refetching stories/sources on the news update signal.
- `frontend-events`: interval polling is replaced by refetching items (current filters intact) on the events update signal.
- `frontend-home`: digest widgets and the weather strip refetch on their respective update signals instead of being fetch-once.

## Impact

- Backend: `app/ws.py` (generalize `ConnectionManager` to topic envelope, drop per-source filter), new app-level WS route (app shell router), `app/scheduler.py` (broadcast pings from news/events cycles, new weather job), `app/news/refresh.py` / `app/events/refresh.py` (report whether data changed), `app/weather/service.py` (change detection), `app/api/timeseries.py` (remove `/ws` route).
- Frontend: `frontend/src/lib/ws.ts` (or a new `lib/live.ts`) singleton bus; `features/timeseries/live.ts`, `features/news`, `features/events`, `features/home` subscription wiring; `App.svelte` shell registration; removal of `setInterval` timers in `NewsFeed.svelte` / `EventsPage.svelte`.
- No new dependencies. Single-deploy artifact (frontend is bundled with the backend), so the endpoint move is not externally breaking in practice.
