## Context

Two manual refresh controls live in feature toolbars today:

- News (`/`): a "Refresh feeds" button in `NewsFeed.svelte`'s toolbar, beside a `<span class="status">` bound to `news.statusText`, disabled while `news.refreshing`. Calls `refreshFeeds()` from the news `api.ts`.
- Events (`/events`): a "Refresh sources" button in `EventsPage.svelte`'s toolbar with the same status/disabled pattern, calling `refreshSources()`.

Both feeds already auto-reload every 5 minutes via `setInterval`, so these buttons are occasional operator/debug affordances. The shell debug overlay (`frontend/src/lib/DebugPanel.svelte`, backed by the `debug` singleton in `frontend/src/lib/debug.svelte.ts`) is the established home for in-app tooling, and it is already route-aware (map section on `/map`, placeholder elsewhere).

The binding constraint: **`lib/` imports from no feature** (AGENTS.md import rules). `DebugPanel` lives in `lib/`, so it cannot import `refreshFeeds` / `refreshSources`. The existing map-viewport debug section already works around this by having the feature *write* runtime state into the `debug` lib slice while the panel only *reads* it (`setMapViewport` / `clearMapViewport`). This change extends that same pattern from passive state to invocable actions.

## Goals / Non-Goals

**Goals:**
- Move both manual refreshes into the debug panel with their status text and disabled-while-refreshing behavior intact.
- Preserve the `lib/`-imports-no-feature isolation rule — no feature import into `lib/`.
- Keep route-awareness without hardcoding feature knowledge in the shell: the panel shows the current route's refresh and nothing else.
- Keep the pattern generic so future feature debug actions register the same way.

**Non-Goals:**
- Changing `refreshFeeds` / `refreshSources` behavior or the `/api/v1/*/refresh` endpoints.
- Changing the 5-minute auto-reload on either feed.
- Adding a manual refresh to `/map` (timeseries is WebSocket-live).
- Reworking the debug modal's toggle, placement, or the existing map section.

## Decisions

### Decision: A feature-action registry in the `debug` lib slice

Add an actions registry to `DebugState`: a reactive list of registered actions, plus `registerAction(action)` and `unregisterAction(action)` (or a single `register` returning a disposer). A feature calls `registerAction` in `onMount` and `unregisterAction` in the returned teardown, exactly mirroring `setMapViewport` / `clearMapViewport`. `DebugPanel` iterates the registry and renders one button + status line per action.

**Why over alternatives:**
- *Shell imports feature `index.ts`* — App.svelte may do this, but `DebugPanel` lives in `lib/`, which imports from no feature; re-exporting the refresh fns and importing them into the panel would break that rule and hardcode every feature's refresh into the always-mounted shell. Rejected.
- *Snippet/slot passed from features* — the debug panel is mounted once by `App.svelte` outside the route chain, not nested inside features, so there is no parent-child slot relationship to pass a snippet through. Registration is the idiomatic Svelte-5 way to compose across an unrelated subtree. Rejected.
- *Registry* keeps the isolation intact, makes route-awareness automatic (unmounted feature ⇒ no registered action), and matches the debug store's stated "general by design" intent.

### Decision: Actions carry reactive `disabled` and `status`, not snapshots

The map-viewport slice stores a plain value snapshot. An action must instead stay live: the button greys out the instant `refreshing` flips and the status text ticks through `Fetching feeds… → Updated <time>`. So the registered action exposes `disabled` and `status` as **getters** (e.g. `get disabled() { return news.refreshing }`, `get status() { return news.statusText }`) rather than copied values. Because the feature's `refreshing` / `statusText` remain `$state` in the feature store, reading them through getters inside the panel's render keeps Svelte's reactivity working across the lib boundary — the panel reacts without importing feature code.

### Decision: Action shape

```ts
interface DebugAction {
  id: string;            // stable key, e.g. "news-refresh"
  label: string;         // button text, e.g. "Refresh feeds"
  run: () => void;       // the refresh callback
  get disabled(): boolean;
  get status(): string;  // "" when idle → hidden
}
```

`DebugPanel` renders registered actions as a debug section (button disabled via `disabled`, `onclick={run}`, status shown when non-empty). On routes with a registered action this section replaces the "no debug data for this view" placeholder; the placeholder still shows on routes with neither a map section nor any registered action.

### Decision: Styling stays in global stylesheets

Per the styling contract, the action button/status markup in `DebugPanel` gets semantic classes styled in the global debug stylesheet (theme-aware). The now-removed toolbar refresh button/status styles in the news and events global stylesheets are deleted. No scoped `<style>` blocks are added.

## Risks / Trade-offs

- **Cross-boundary reactivity via getters** → If `disabled`/`status` were captured as plain values at registration time they would go stale. Mitigation: use getters that read the feature `$state` live; verify the button disables mid-refresh and the status updates by driving a real refresh.
- **Registration lifecycle leaks** → A feature that registers but fails to unregister would leave a dead action (and a call into an unmounted component's state). Mitigation: register in `onMount`, unregister in its teardown return, keyed by stable `id`; unregister is idempotent.
- **Discoverability** → Users lose the always-visible refresh button. Accepted: auto-reload runs every 5 min, and the refresh is deliberately reframed as debug tooling.
- **Two features registering** → Only one feature is mounted per route, so at most one action is present at a time; the registry supports N but ordering/dedup is trivial at this scale.

## Migration Plan

Pure frontend change, shipped in one build:
1. Add the registry to `debug.svelte.ts`.
2. Render registered actions in `DebugPanel.svelte` (+ global debug styles).
3. News: remove toolbar button/status; register the action on mount.
4. Events: same.
5. Remove dead toolbar refresh styles.
6. Rebuild the frontend (`vite build` → `static/`) and rebuild Docker.

Rollback is reverting the commit; no data, API, or schema surface is touched.

## Open Questions

None — scope, status placement, and toolbar removal are confirmed.
