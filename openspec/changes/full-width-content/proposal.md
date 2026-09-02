## Why

Every feature page except the map caps its main content at a centered fixed width — 46rem
(~736px) for the news and events feeds, 74rem (~1184px) for the home widget grid. On a wide
display that leaves the majority of the viewport as empty gutter while the content it frames
stays cramped: at 1920px the news feed occupies 38% of the window and the home grid 62%. The
map page already runs edge to edge, so the site is also internally inconsistent about it.

## What Changes

- Remove the `max-width` cap and the centering `margin: 0 auto` from each feature's main
  content region so it fills the page width:
  - `.home-scroll` (`home.css`) — was `max-width: 74rem`
  - `#news main` (`news.css`) — was `max-width: 46rem`
  - `#news .sources` (`news.css`) — was `max-width: 46rem`
  - `#events main` (`events.css`) — was `max-width: 46rem`
- Nothing else changes. Horizontal padding (`16px`), the toolbars and tab bars, card styles and
  spacing, the home widget grid's `auto-fit minmax(20rem, 1fr)` track definition, and the map's
  existing `#layout` are all left exactly as they are.
- Accepted consequence, stated deliberately: story and event cards become one full-width column,
  so their headlines and summaries run to the viewport width rather than to a reading measure.
  Reflowing the feeds into a multi-column card grid is explicitly **not** part of this change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `frontend-styling`: adds a requirement that each route's main content region spans the full
  page width rather than being capped and centered. This belongs in the shared styling contract
  rather than in each feature spec because it is a cross-feature layout rule, and because the
  per-feature specs (`frontend-home`, `frontend-news`, `frontend-events`) never stated a width
  in the first place — their requirements are unaffected.

## Impact

- **Code**: three stylesheets — `frontend/src/styles/home.css`, `frontend/src/styles/news.css`,
  `frontend/src/styles/events.css`. CSS only; no Svelte component, markup, or TypeScript edits.
- **Routes affected**: `/` (home), `/news`, `/events`. `/map` is already full width and is not
  touched.
- **Not affected**: backend, API, database, dependencies, build config. No new selectors or
  markup hooks, so the styling contract's semantic-substrate rules are unchanged.
- **Themes**: both light and dark themes are token-driven and carry no width rules, so neither
  needs updating.
