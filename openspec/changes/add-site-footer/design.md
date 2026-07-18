# Design: Add Site Footer

## Context

The app shell is viewport-locked: `#app` is a full-height flex column (header on top, the active
route's region filling the remainder via `flex: 1`), and there is **no page-level scroll**. Each
content route owns its own scroll container — `.home-scroll` (home), `#news` (news), `#events`
(events) — all `flex: 1; min-height: 0; overflow-y: auto`. The map route's `#layout` fills the
viewport and does not scroll at all.

The requested footer must sit **at the bottom of the page's content** (reached by scrolling), not
in a fixed always-visible position. Given the shell layout, the only place "after the content"
exists is inside each route's scroll container.

The news page already has a page-specific "sources footer" (feed health) at the end of `#news`;
the site footer is a separate, unrelated element that flows after it.

## Goals / Non-Goals

**Goals:**

- A site footer with one link — text "100% Open Source" → `https://github.com/driverdan/localdash` —
  at the end of the scrollable content on the home, news, and events routes.
- One shared component; no per-route duplication of markup.
- Token-only styling so every theme inherits it for free.

**Non-Goals:**

- No footer on the map route (viewport-locked tool, no content flow).
- No restructuring of the shell scroll model (a shared scrolling `<main>` was considered and
  rejected — see Decisions).
- No additional footer content (license text, version, nav links) — one link only.

## Decisions

### 1. Footer flows inside each route's scroll region, not at shell level

A shell-level `<footer>` in `App.svelte` after the route block would sit below regions that are
`flex: 1` — making it a fixed, always-visible strip, which is explicitly not wanted. The
alternative of restructuring to one shared scrolling `<main>` (routes size naturally, footer
flows after) would unwind the documented "each region owns its scroll" contract in `base.css`
that every route's CSS is built on, and the map still couldn't participate. Far too much surgery
for a footer. So the footer renders as the **last child of each scrolling region**.

### 2. Shared `SiteFooter.svelte` component in `frontend/src/lib/`

Three render sites (home, news, events) with one source of truth for the markup, link text, and
URL. `lib/` is the correct home per the import rules: features may import from `lib/`, and `lib/`
imports from no feature. The component is purely presentational — semantic `<footer>` element, no
props, no state.

### 3. Link opens in a new tab

`target="_blank" rel="noopener"` — navigating the SPA away in-place would tear down the live
WebSocket bus and all in-memory state for no reason.

### 4. Styling in `base.css` via tokens

The footer is shell chrome (like the header), so its rules live in `base.css` beside the other
shell styles, scoped to a `.site-footer` class on the `<footer>` element: centered, small type,
`--color-text-muted`, modest padding. Token-only styling means `theme-dark.css` and all other
themes need no additional rules.

### 5. Map route excluded

`#layout` has no scrollable content flow — there is no "bottom of the content" to place a footer
at. Overlaying the map corner would fight Leaflet attribution/controls, and the sidebar is a
filter panel, not page content. Full-viewport map tools conventionally have no footer.

## Risks / Trade-offs

- **[Footer missing on the map route]** → Accepted deliberately; the GitHub link is one click
  away on any other route, including home, the landing page.
- **[Drift across render sites]** (a future route forgets the footer) → Single shared component
  keeps the cost of adding it to one line; the spec delta documents which routes carry it.
- **[News page has two footers]** (feed-health sources footer + site footer) → They are visually
  distinct (the sources footer is a bordered panel; the site footer is a small muted line) and
  the site footer always renders last.
