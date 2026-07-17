# frontend-live Specification

## Purpose

The frontend's singleton live-update client (`frontend/src/lib/live.svelte.ts`): the app's one
WebSocket connection to `/api/v1/ws`, the topic subscription bus features consume, shared reactive
connection state for the shell's status indicator, and reconnect-refetch semantics. The frontend
counterpart of the `live-updates` spec; lives in `lib/` so every feature can use it without
cross-feature imports.

## Requirements

### Requirement: Singleton connection with topic subscription bus
The frontend SHALL maintain exactly one WebSocket connection to `/api/v1/ws` for the whole app, owned by a module in `frontend/src/lib/` (feature-agnostic, importable by every feature without cross-feature imports). The module SHALL expose `subscribe(topic, handler)` returning a disposer: each incoming message is dispatched to all handlers registered for its `topic`; messages with no registered handlers (including unknown future topics) are ignored. The connection SHALL reconnect automatically ~3 seconds after any close, following the page protocol (`ws`/`wss`).

#### Scenario: Messages dispatch by topic
- **WHEN** a `{topic: "news", type: "updated"}` message arrives and handlers are registered for `news` and `events`
- **THEN** only the `news` handlers run

#### Scenario: Unknown topics are ignored
- **WHEN** a message arrives with a topic no handler is registered for
- **THEN** it is dropped without error

#### Scenario: One socket regardless of subscriber count
- **WHEN** multiple features subscribe to topics
- **THEN** the browser holds a single WebSocket connection to `/api/v1/ws`

### Requirement: Shared connection state
The bus SHALL expose the reactive connection state (`connecting` / `live` / `disconnected`) as the single source for connection indicators; features SHALL NOT track their own socket state. The app shell's status indicator SHALL reflect this shared state.

#### Scenario: Indicator follows the shared socket
- **WHEN** the single connection drops and later reconnects
- **THEN** the indicator shows the disconnected state and returns to "live" on reconnect, on whichever route displays it

### Requirement: Reconnect triggers refetch, not replay
The bus SHALL notify registered reconnect handlers on each `disconnected → live` transition that follows the first successful connect (the boot-time connect fires no reconnect notification, so initial on-mount loads are not duplicated). Subscribed features SHALL respond by refetching their data through their existing REST loaders, recovering any updates missed while disconnected. There is no server-side message replay.

#### Scenario: Missed pings are recovered by refetch
- **WHEN** the connection drops, a news cycle completes server-side, and the connection later reconnects
- **THEN** the news store refetches and shows the new stories despite the missed ping

#### Scenario: Boot connect does not double-load
- **WHEN** the app starts and the socket connects for the first time
- **THEN** no reconnect notification fires; features load once via their normal on-mount fetches

### Requirement: Permanent feature subscriptions registered from the shell
The app shell SHALL start the connection and register each feature's live subscriptions once at startup. News, events, and home subscriptions SHALL be permanent (not tied to route mounts), refetching into their module-singleton stores so any route is current when navigated to. Route-scoped subscriptions (timeseries) SHALL use the same bus with mount-scoped disposers.

#### Scenario: Background route stays fresh
- **WHEN** the user is on `/map` and a `news` ping arrives
- **THEN** the news store refetches in the background, and navigating to `/news` shows the new stories without waiting for a fetch triggered by the navigation

#### Scenario: Subscriptions do not accumulate
- **WHEN** the user navigates between routes repeatedly
- **THEN** permanent subscriptions are registered exactly once and mount-scoped subscriptions are disposed on unmount
