## Why

The manual "Refresh feeds" (news) and "Refresh sources" (events) buttons sit in each feature's primary toolbar, but both feeds already auto-reload every 5 minutes — the manual triggers are operator/debug affordances, not everyday controls. Moving them into the shell debug panel declutters the feature toolbars and puts occasional-use tooling where the rest of the in-app debugging lives.

## What Changes

- Introduce a **debug actions registry** in the shell debug store (`frontend/src/lib/debug.svelte.ts`): a feature registers a labelled action (with a run callback, a reactive disabled flag, and reactive status text) on mount and unregisters it on teardown, mirroring the existing map-viewport write-to-lib-slice pattern. `DebugPanel` reads the registry and renders each action as a button plus its status line.
- Route-awareness falls out for free: only the currently mounted feature has a registered action, so the debug panel shows exactly the current route's refresh (news on `/`, events on `/events`, nothing on `/map`).
- **News**: remove the "Refresh feeds" button and its status span from the feed toolbar; register the refresh (with its `Fetching feeds… / Updated <time> / Refresh failed` status and disabled-while-refreshing state) as a debug action instead.
- **Events**: remove the "Refresh sources" button and its status span from the events toolbar; register the refresh as a debug action the same way.
- The debug panel's non-map placeholder ("no debug data for this view") is superseded on `/` and `/events` by the registered refresh action.
- No change to `/map` (timeseries is WebSocket-live and has no manual refresh) and no change to the auto-reload behavior on either feed.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `frontend-debug`: the debug store gains a feature-action registry, and the debug panel renders registered feature actions (button + reactive status) as route-aware sections.
- `frontend-news`: the "Refresh feeds" control moves out of the feed toolbar; the feed registers it as a debug action instead of rendering it inline.
- `frontend-events`: the "Refresh sources" control moves out of the events toolbar; the feature registers it as a debug action instead of rendering it inline.

## Impact

- `frontend/src/lib/debug.svelte.ts` — new action-registry slice (types + register/unregister).
- `frontend/src/lib/DebugPanel.svelte` — renders registered actions and their status.
- `frontend/src/features/news/components/NewsFeed.svelte` — drop the button + status span from the toolbar; register/unregister the refresh action on mount/teardown.
- `frontend/src/features/events/components/EventsPage.svelte` — same for the events refresh.
- Global stylesheets for the debug panel (and the news/events toolbars) — style the action buttons/status in the panel; remove now-unused toolbar refresh styling per the styling contract.
- No backend, API, or dependency changes; `refreshFeeds` / `refreshSources` in the feature `api.ts` modules keep their current behavior.
