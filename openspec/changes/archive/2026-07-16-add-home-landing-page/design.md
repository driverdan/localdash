## Context

The shell (`App.svelte`) holds a three-entry route table over a minimal path router: `/` → `NewsFeed`, `/map` → `TimeseriesDashboard`, `/events` → `EventsPage`. Features live in isolated namespaces under `frontend/src/features/`, exposing only an `index.ts` public surface; global styles live in `frontend/src/styles/*.css` imported from `main.ts`.

Data facts that shape this design:

- `/api/v1/events/items` already supports `limit`, `upcoming=true` (default), ordered by `starts_at` ascending — "next 5 events" needs no backend work.
- `/api/v1/news/stories` returns all stories in the `hours` window, sorted newest-first, plus the `categories` label map. It has no `limit` parameter.
- The events feature persists topic/distance filters in localStorage and its `items` state is always the filtered view; the news feature persists category tab and hours window. The home page must not inherit any of these.
- `StoryCard` renders the category badge via the news feature's `news.categories` label map; it falls back to the raw slug when a label is missing.

## Goals / Non-Goals

**Goals:**
- `/` renders a new home landing page; the news feed moves to `/news` unchanged.
- Home shows the 5 newest stories and the next 5 upcoming events using the existing `StoryCard`/`EventCard`, each in a widget card with a "view all" link.
- Home data is independent and unfiltered — its own state, its own fetches.
- Layout accommodates future widgets (weather, timeseries summary) as additional cards.
- Stories API gains an optional `limit` so the home payload stays small.

**Non-Goals:**
- No compact/summary card variants — cards render exactly as they do on their feature pages.
- No widget framework, registry, or user-configurable layout — two hardcoded cards in a grid.
- No redirect from `/` for old news bookmarks; news is one nav click away.
- No auto-refresh polling loop on home beyond initial load (can be added later if it earns its keep).
- No new backend endpoints; no weather/timeseries work.

## Decisions

### 1. New `features/home` namespace with its own slim state

Home is a peer feature (`frontend/src/features/home/` with `api.ts`, `state.svelte.ts`, `components/HomePage.svelte`, `index.ts` exporting only `HomePage`). It fetches `/api/v1/news/stories?limit=5` and `/api/v1/events/items?limit=5` directly into its own state.

*Alternative rejected:* importing `news`/`events` feature state and slicing. The events state is always the *filtered* view (saved topics/distance would leak into the digest), and coupling home to two features' internals contradicts the namespace-isolation contract.

### 2. Reuse cards by widening the news/events public surfaces

`features/news/index.ts` additionally exports `StoryCard` (and the `Story` type); `features/events/index.ts` additionally exports `EventCard` (and the `EventItem` type). Home imports only those public surfaces — never `../news/components/...` internals.

*Alternative rejected:* duplicating card markup in home (drifts immediately) or deep-importing internals (breaks the isolation rule the shell spec establishes).

### 3. Category labels: home feeds the shared label map

`StoryCard` reads `news.categories` for badge labels. Home's stories response includes the same `categories` map, so the news feature exports a narrow setter (e.g. `setCategoryLabels(map)`) from its index, and home's loader calls it with the fetched map. Visiting `/news` later overwrites it with an identical value — the map is server-defined, not a user preference, so no filter leakage.

*Alternatives rejected:* accepting the raw-slug fallback (visibly wrong badges on first landing), or adding a `categories` prop to `StoryCard` (touches every existing call site for a value that is global anyway).

### 4. Route table and nav

`App.svelte` gains `onHome = currentPath() === "/"` and `onNews = currentPath() === "/news"`. Nav order: **Home** (`/`), **News** (`/news`), **Map** (`/map`), **Events** (`/events`). The 404 fallback copy becomes "go to the home page" linking `/`. The router (`lib/router.svelte.ts`) needs no changes.

### 5. Stories API `limit`

`GET /api/v1/news/stories` accepts `limit: int | None = Query(None, ge=1)`. Since clustering happens in Python over the windowed article set, the limit is applied by slicing the sorted story list before returning (not a SQL `LIMIT` — stories are clusters, not rows). Omitted → current behavior, so `/news` is untouched.

### 6. Layout and styles

`HomePage.svelte` renders a `<section class="home-grid">` of `<article class="widget">` cards, each with a header (`<h2>` + "view all →" link using the router's `navigate`). Grid uses `repeat(auto-fit, minmax(...))` so a third/fourth widget later is a pure addition. Styles go in a new `frontend/src/styles/home.css` imported from `main.ts`, following the global-styling contract (plain global CSS, theme variables, externally overridable).

### 7. Loading/error handling

Each widget loads independently: a failed stories fetch shows an inline error in the news widget while the events widget still renders (and vice versa). Empty results show a quiet empty state ("No upcoming events"). No debug-panel refresh action for home — the per-feature refresh actions remain scoped to their own routes.

## Risks / Trade-offs

- [Bookmarks to `/` expecting news land on home] → Accepted; nav makes news one click away, and the digest itself shows the latest stories.
- [Wider public surfaces let other features import cards] → Acceptable: exports are still funneled through `index.ts`, keeping the isolation boundary auditable.
- [Full-size cards may feel heavy in a two-column digest] → Accepted per product decision; CSS can constrain image height inside `.widget` without forking the components.
- [Home data goes stale while the tab sits open] → Accepted for v1 (no polling); revisit when more widgets arrive.
- [`limit` slicing happens after clustering] → Fine at this scale; the expensive part (windowed fetch + clustering) already runs on every `/news` load today.

## Migration Plan

Single deploy; no data migration. Rollback = revert the commit. The only externally visible break is the `/` → `/news` route move, which is client-side only (FastAPI serves the same SPA bundle for both).

## Open Questions

None — product decisions (stories not articles, ignore saved filters, two widgets, reuse cards as-is) were settled during exploration.
