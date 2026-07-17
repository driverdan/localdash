## Context

Freshness works three different ways today:

- **timeseries**: APScheduler collector ticks run fetch→ingest→`Diff`, and `run_collector` broadcasts the diff over `/api/v1/timeseries/ws` (`app/ws.py` `ConnectionManager`); `features/timeseries/live.ts` applies `new`/`updated`/`closed` incrementally to the map store.
- **news / events**: the server refreshes on its own schedule (`news_refresh_minutes` / `events_refresh_minutes`) but emits no signal; `NewsFeed.svelte` and `EventsPage.svelte` run their own 5-minute `setInterval` re-fetches, disconnected from when data actually changed.
- **weather / home**: the weather payload is a lazy TTL cache (`app/weather/service.py`) refreshed only when a request arrives; the home page fetches its digests once on mount and never again.

Constraints that shape the design:

- Events filtering (topics, max-miles geo distance, search) is deliberately server-side — the client refetches `/items` rather than filtering a cached superset. News reclusters stories each cycle, so per-item diffs aren't stable. Pushing raw data for these features would force filter/cluster logic into the client.
- The frontend is bundled into the backend image (single deploy), so moving the WebSocket endpoint is not externally breaking.
- Single-user LAN dashboard: client counts are tiny; simplicity beats scalability concerns.

## Goals / Non-Goals

**Goals:**

- One WebSocket connection per browser tab that carries update signals for every feature.
- UI updates automatically for news, events, home digests, and weather — no interval polling, no stale-until-reload widgets.
- Preserve the timeseries incremental-diff behavior and the server-side filtering architecture of news/events.
- Manual refreshes (debug-panel actions, `POST .../refresh`) produce the same signals as scheduled ones.

**Non-Goals:**

- Per-client topic subscription filtering (every client receives every message; filtering happens client-side, as the timeseries frontend already does per-source).
- Pushing data payloads for news/events/weather (pings + REST refetch instead).
- Replacing the initial on-mount REST loads or the loading-state choreography — the bus keeps stores fresh; first paint still comes from the existing fetch paths.
- Offline queueing / missed-message replay (reconnect triggers a refetch instead).

## Decisions

### 1. Hybrid payloads: diffs for timeseries, invalidation pings for everything else

Timeseries keeps pushing full diffs — the entity-keyed store and incremental marker updates depend on them. News, events, and weather get `{topic, type: "updated"}` pings; the client refetches through the same REST endpoints it already uses, current filters intact.

*Alternative considered*: data-push for all topics. Rejected because events filtering is server-side (geo distance especially) and news cluster identity shifts wholesale on recluster — the client would need to reimplement server logic to place pushed items. Ping+refetch has identical server cost to today's polling, but fires exactly when something changed.

### 2. One endpoint at `/api/v1/ws`, owned by the app shell; topic envelope

New WebSocket route directly under `/api/v1` (feature-agnostic endpoints live there per the app-shell convention — implemented in `app/api/root.py`). Every message carries a `topic` field:

```
{topic: "timeseries", type: "diff", source, new, updated, closed}   ← data
{topic: "news",       type: "updated"}                              ← ping
{topic: "events",     type: "updated"}                              ← ping
{topic: "weather",    type: "updated"}                              ← ping
```

`Diff.to_message()` gains the `topic` key. `/api/v1/timeseries/ws` is removed outright (no deprecation window — single-deploy artifact), and `ConnectionManager` drops the per-source subscription map (the bundled frontend never passed `source`) down to a plain set of sockets with lock-guarded broadcast.

### 3. Signals are emitted at each feature's refresh choke point

Mirroring how `run_collector` is the shared path for scheduled *and* manual timeseries refreshes, the ping broadcast goes where scheduled and manual paths already converge: inside `app/news/refresh.py::refresh()` and `app/events/refresh.py::refresh()` (both are called by the scheduler jobs and the `POST .../refresh` routes). This guarantees debug-panel refreshes light up the UI too, with no duplicated emission at call sites.

- **events**: ping only when the cycle changed data — any of `created`, `merged`, `resolved`, or `reconciled` nonzero (all already counted in `stats`).
- **news**: ping after every completed cycle. Reclustering makes "did anything meaningfully change" fuzzy; an every-cycle ping costs one stories+sources refetch per `news_refresh_minutes` — the same load as today's polling, better timed. Change-hashing can come later if it ever matters.

*Alternative considered*: broadcast from the scheduler wrappers only. Rejected: manual refreshes would silently not update the UI.

### 4. Weather gets a scheduled proactive refresh job

The weather cache refreshes only on request today — if the client waits for a ping before refetching, nothing ever pings (deadlock). Add an APScheduler job at the `weather_cache_minutes` interval (guarded by `weather_enabled`) that asks `WeatherService` for the current payload and broadcasts a `weather` ping when the shaped payload differs from the previous one. Embedded observation timestamps mean most cycles differ — that's fine; the refetch hits the just-warmed cache. Failures log and skip the ping (stale payload → no signal), matching the other jobs' error isolation.

### 5. Frontend: singleton bus in `lib/live.svelte.ts`, wrapping the existing `connectWebSocket`

`lib/ws.ts` stays as the low-level reconnecting-socket helper. A new `lib/live.svelte.ts` owns the app's single connection to `/api/v1/ws` and exposes:

- `subscribe(topic, handler): disposer` — dispatches parsed messages by `msg.topic` to all handlers for that topic; unknown topics are ignored (forward-compatible).
- Reactive connection state (`connecting | live | disconnected`) replacing the timeseries-owned `ts.connection` as the source for the shell's status indicator.
- `onReconnect(handler): disposer` — fires on `disconnected → live` transitions **after** the first successful connect (boot-time connect must not double-fire the on-mount loads).

The shell (`App.svelte`) starts the connection and calls each feature's exported registration function once at module setup.

### 6. Subscription lifetimes differ by feature, deliberately

- **news / events / home**: permanent subscriptions registered from the shell. Handlers refetch into the module-singleton stores (`loadStories()`+`loadSources()`, `loadItems()`, home digest loaders), so navigating to a route always shows current data. The same loaders run on reconnect. The 5-minute `setInterval`s in `NewsFeed.svelte` / `EventsPage.svelte` are deleted; on-mount initial loads stay.
- **timeseries**: mount-scoped subscription (`connectLive()` becomes `subscribe("timeseries", …)` via the bus, disposed on unmount) — unchanged semantics. The dashboard already calls `loadActive()` on every mount, so an off-route subscription would buy nothing while risking diff application against a store whose source-selection state isn't loaded yet. Reconnect while mounted re-runs `loadActive()` to recover missed diffs (an improvement — today a reconnect can miss diffs silently).
- **home weather strip**: subscribes to `weather` pings and re-runs `loadWeather()`.

## Risks / Trade-offs

- [News pings every cycle even when nothing changed] → Refetch cost equals today's polling; acceptable. Revisit with a content hash only if it becomes noisy.
- [Events refetch races a user's in-flight filter change] → The handlers call the existing loaders, which already serialize per-feature state writes; last response wins, and filters are query params so any response matches the filters it was asked with. Same exposure as today's interval polling.
- [Permanent handlers refetch for routes the user never visits] → A few small JSON fetches per refresh interval on a LAN; accepted for instant-fresh navigation.
- [Weather payload comparison pings on cosmetic timestamp changes] → Harmless extra refetch against a warm cache; noted as a candidate for field-level comparison later.
- [Global connection state indicator now reflects all features, shown only on the map route today] → Keep the indicator sourced from the bus; whether to show it on all routes is a UI choice made in tasks (default: show it globally, since the socket now serves every route).
- [Removing `/api/v1/timeseries/ws` breaks any out-of-tree client] → None known; the spec explicitly treats the bundled frontend as the only consumer, and news of the removal lives in the spec delta.

## Migration Plan

Single deploy: backend endpoint move and frontend bus land in the same image (`docker compose up --build`). No data migration. Rollback = redeploy previous image. In-flight browser tabs from the old build reconnect against the removed endpoint and fail until reloaded; the no-cache static serving picks up the new bundle on next load.

## Open Questions

- None blocking. The connection-indicator placement (map-only vs. global) is a cosmetic call deferred to implementation; default is global.
