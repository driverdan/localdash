## 1. Markup

- [x] 1.1 In `HomePage.svelte`, move `<WeatherStrip />` from above `.home-grid` into the grid: wrap it and the events `<article class="widget">` in a `<div class="widget-column">` grid item after the news widget
- [x] 1.2 In `WeatherStrip.svelte`, restructure the root as `<article class="widget">` with a `.widget-head` containing `<h2>Weather</h2>` (no view-all link) and a widget body holding the current-conditions block and periods; keep loading/error/partial rendering logic unchanged

## 2. Styles

- [x] 2.1 In `home.css`, add the `.widget-column` rule (flex column, `gap: 20px`, `min-width: 0`) and update the `.home-scroll` comment that explains why the strip sat outside the grid (no longer applicable)
- [x] 2.2 Replace the `.weather-strip` horizontal-bar rules with widget-consistent rules: drop the outer panel background/border/wrap-flex, keep the current-conditions styling (icon, temp, meta), and style periods as vertically stacked rows

## 3. Verify

- [x] 3.1 Rebuild and run via `sg docker -c 'docker compose up --build'`, then check the homepage: wide viewport shows news beside weather-over-events with a matching "Weather" header; narrow viewport stacks news, weather, events
- [x] 3.2 Check degraded states still render inside the widget (loading notice, simulated weather failure leaves news/events intact) and run frontend checks (`svelte-check` / build)
