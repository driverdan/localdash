# Add Site Footer

## Why

LocalDash is open source but the running site never says so — nothing in the UI links back to
the GitHub repository, so visitors have no path from the dashboard to the code. A small site
footer with a "100% Open Source" link fixes that with near-zero UI cost.

## What Changes

- Add a shared `SiteFooter` component (in `frontend/src/lib/`) containing a single link,
  text **"100% Open Source"**, pointing at `https://github.com/driverdan/localdash`, opening
  in a new tab so in-app state (the live WebSocket) is not torn down.
- Render the footer **in the flow of each route's scrollable content** — as the last element
  inside the home, news, and events scroll regions — so it appears after the content when the
  user scrolls to the bottom, not as a fixed always-visible strip.
- The map route (`/map`) is excluded: it is a viewport-locked full-screen tool with no
  content flow, so it has no natural "bottom of content" for a footer.
- Style the footer in `base.css` via existing design tokens (muted small text), so all themes
  inherit it with no per-theme rules.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `frontend-shell`: new requirement — the shell provides a site footer (open-source
  attribution link) rendered at the end of the scrollable content on content routes
  (home, news, events), excluded from the viewport-locked map route.

## Impact

- **Frontend only** — no backend, API, or schema changes.
- New file: `frontend/src/lib/SiteFooter.svelte`.
- One-line render additions in the home, news, and events page components (each already
  imports from `lib/`, so import rules are respected).
- Footer styles added to `frontend/src/styles/base.css` (tokens only; `theme-dark.css`
  untouched).
- No new dependencies; `static/` rebuild via the normal frontend build.
