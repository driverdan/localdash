## 1. Debug store: action registry

- [ ] 1.1 In `frontend/src/lib/debug.svelte.ts`, add a `DebugAction` interface (`id`, `label`, `run`, `get disabled()`, `get status()`) and a reactive `actions` list on `DebugState`.
- [ ] 1.2 Add `registerAction(action)` and `unregisterAction(id)` methods (register replaces any existing action with the same id; unregister is idempotent), mirroring the `setMapViewport`/`clearMapViewport` pattern.

## 2. Debug panel rendering

- [ ] 2.1 In `frontend/src/lib/DebugPanel.svelte`, render each registered action as a debug section: a button (`onclick={action.run}`, `disabled={action.disabled}`) showing `action.label`, plus the `action.status` text shown only when non-empty. Use semantic classes (no scoped `<style>`).
- [ ] 2.2 Adjust the placeholder logic so "no debug data for this view" shows only when there is neither a shell section (map) nor any registered action.
- [ ] 2.3 Add theme-aware styling for the action button + status to the global debug stylesheet.

## 3. News feature

- [ ] 3.1 In `NewsFeed.svelte`, remove the "Refresh feeds" `<button>` and its `<span class="status">` from the toolbar.
- [ ] 3.2 In `onMount`, register a debug action `{ id: "news-refresh", label: "Refresh feeds", run: refreshFeeds, get disabled() { return news.refreshing }, get status() { return news.statusText } }`; unregister it in the teardown return.

## 4. Events feature

- [ ] 4.1 In `EventsPage.svelte`, remove the "Refresh sources" `<button>` and its `<span class="status">` from the toolbar.
- [ ] 4.2 In `onMount`, register a debug action `{ id: "events-refresh", label: "Refresh sources", run: refreshSources, get disabled() { return events.refreshing }, get status() { return events.statusText } }`; unregister it in the teardown return.

## 5. Styling cleanup

- [ ] 5.1 Remove now-unused refresh button/status styles from the global news and events stylesheets (keep the toolbar layout correct without them).

## 6. Verify

- [ ] 6.1 `vite build` succeeds with no type errors; rebuild Docker (`docker compose up --build`).
- [ ] 6.2 On `/`: no refresh button in the toolbar; the debug panel shows a working "Refresh feeds" action that disables mid-refresh and updates its status text.
- [ ] 6.3 On `/events`: no refresh button in the toolbar; the debug panel shows a working "Refresh sources" action that disables mid-refresh and updates its status.
- [ ] 6.4 On `/map`: debug panel still shows the map section and no refresh action; navigating between routes registers/unregisters actions correctly (no stale action after leaving a route).
