# Add Site Footer to Map Sidebar

## Why

The map route is the only route with no open-source attribution link. It was excluded when the
footer was introduced because a viewport-locked full-screen map has no content flow — but that
reasoning looked only at the map pane. The route's sidebar is an ordinary `overflow-y: auto`
scroll region with a natural bottom, so the exclusion premise was too broad and the map route
can carry the footer the same way every other route does.

## What Changes

- Render the existing shared `SiteFooter` component on the map route, as the last child of the
  sidebar (`#sidebar`), after the incident table.
- The footer flows in the sidebar's existing scroll region with **no special treatment** — no
  pinning, no `position: sticky`, no `margin-top: auto`, no new or modified CSS. It appears
  wherever the sidebar content ends and is reached by scrolling, exactly like the home, news,
  and events routes.
- Amend the `frontend-shell` site-footer requirement so the map route is no longer excluded.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `frontend-shell`: the "Site footer with open-source attribution" requirement currently states
  that the viewport-locked map route SHALL NOT render the site footer, with a matching
  "Map route has no footer" scenario. The requirement changes to include the map route, rendering
  the footer at the end of its sidebar scroll region, and the exclusion scenario is replaced by
  one covering the sidebar footer.

## Impact

- **Frontend only** — no backend, API, schema, or dependency changes.
- One import and one render line in
  `frontend/src/features/timeseries/components/Dashboard.svelte`.
- No stylesheet changes: `frontend/src/styles/base.css` (`.site-footer`) and
  `frontend/src/styles/timeseries.css` (`#sidebar`) are untouched.
- No new files; `SiteFooter.svelte` is reused as-is. Its component comment, which names the map
  as excluded, needs updating to stay accurate.
- `static/` rebuild via the normal frontend build.
