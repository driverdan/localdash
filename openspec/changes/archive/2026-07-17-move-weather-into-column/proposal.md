## Why

The weather strip currently spans the full content width above the news/events widget grid, which gives a small amount of information an outsized share of the page and pushes the digests down. Moving weather into the right column above the events widget makes the homepage denser and visually consistent — three matching widgets instead of a bar plus a grid.

## What Changes

- The weather display moves from a full-width strip above the widget grid into the right column of the grid, directly above the "Upcoming events" widget.
- Structurally, weather and events are wrapped in a single column container that is one grid item, so the existing `auto-fit` grid behavior (future widgets are pure additions) is preserved.
- The weather display is restyled as a proper widget: it gains a `.widget-head`-style "Weather" header matching the news/events widgets, and forecast periods stack as rows instead of flowing horizontally.
- When the grid collapses to one column on narrow viewports, the order becomes news → weather → events (weather no longer sits above everything).
- No behavior changes to data fetching, live updates, error/empty handling, or the weather API.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `frontend-home`: The "Current weather strip" requirement becomes a "Weather widget" requirement — placement changes from a full-width strip above the grid to the right column above the events widget, with a widget header and stacked forecast periods. The "Widget grid landing page" requirement's layout description updates to match (weather lives inside the grid's right column; narrow-viewport stacking order is news, weather, events). Fetching, live-update, and failure-isolation behavior are unchanged.

## Impact

- `frontend/src/features/home/components/HomePage.svelte` — move `<WeatherStrip />` inside the grid, wrapped with the events widget in a column container.
- `frontend/src/features/home/components/WeatherStrip.svelte` — add the widget header; markup tweaks for stacked periods.
- `frontend/src/styles/home.css` — column-container rule, widget-style weather rules, removal of the full-width strip layout rules and the now-obsolete comment about spanning items pinning auto-fit tracks open.
- No backend, API, or state changes.
