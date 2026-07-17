## Context

The homepage (`frontend/src/features/home/`) renders `<WeatherStrip />` as a full-width sibling *above* `.home-grid`, which lays out the news and events widgets with `repeat(auto-fit, minmax(20rem, 1fr))`. The strip is deliberately outside the grid: a full-width item spanning an auto-fit grid pins its empty trailing tracks open (documented in `home.css`). The strip is a horizontal wrap-flex bar; the two widgets share a common `.widget` / `.widget-head` visual language that weather currently does not use.

The change moves weather into the right column, directly above events, and makes it look like a third widget.

## Goals / Non-Goals

**Goals:**
- Weather renders in the grid's right column above the events widget on wide viewports.
- Weather adopts the widget visual language: a `.widget-head` header reading "Weather", forecast periods stacked vertically as rows.
- The grid's auto-fit property survives — a future third top-level widget remains a pure addition.
- No changes to data fetching, home state, live-update subscriptions, or error/empty semantics.

**Non-Goals:**
- No weather feature page or "view all" link (there is no `/weather` route; the head has a title only).
- No preservation of weather-first ordering on narrow viewports — the collapsed single-column order becomes news → weather → events, accepted in the proposal.
- No rewording of the `frontend-home` live-updates requirement ("weather strip" mentions there are cosmetic; behavior is unchanged, and scenario renames are a known archive blocker in this repo).

## Decisions

**Column container over `grid-template-areas`.** Weather and events wrap in a single `<div class="widget-column">` that is one grid item, itself a flex column (`display: flex; flex-direction: column; gap: 20px`). Alternative considered: explicit `grid-template-areas` placing weather/events in a named right column — rejected because it abandons the auto-fit layout the CSS deliberately preserves for future widgets, and it complicates the narrow-viewport collapse. With the wrapper, the grid still sees exactly two items (news widget, widget-column) and collapses naturally.

**Weather becomes a `.widget` with a header.** `WeatherStrip.svelte` renders `<article class="widget">` containing a `.widget-head` (an `<h2>Weather</h2>`, no view-all link) and a body. This reuses the existing `.widget-head` rules in `home.css` verbatim — no new header styling. The component keeps its name and file; only markup and classes change (renaming the file would touch imports for no behavioral gain — can be revisited later).

**Periods stack as rows.** The weather body becomes a vertical flex stack: the current-conditions block first, then each forecast period as a full-width row (period name and detail on their own lines, as today, but rows no longer flow horizontally). The old `.weather-strip` horizontal bar rules (wrap-flex, `gap: 8px 28px`, panel background/border on the outer element) are replaced by widget-consistent rules; current-conditions inner styling (icon, big temp, meta line) carries over.

**Loading/error/empty states are unchanged in substance.** The one-line notices now render inside the widget body under the "Weather" header instead of inside a full-width bar. Failure isolation (weather failing never touches news/events) is untouched — it lives in state/fetch code, which this change does not modify.

## Risks / Trade-offs

- [Weather drops below the full news digest on narrow viewports] → Accepted in the proposal; if it proves annoying on phones, a follow-up media query can reorder, but that is out of scope here.
- [Delta uses REMOVED + ADDED for the weather requirement instead of RENAMED] → Intentional: `openspec archive` blocks renamed scenarios in this repo, and the requirement's placement scenarios change materially anyway. The REMOVED entry carries Reason/Migration pointing at the new requirement.
- [Squeezing current conditions into a ~half-width column could wrap awkwardly] → The current-conditions block already handles narrow widths (it wraps today on small screens); stacked periods remove the widest horizontal element.
