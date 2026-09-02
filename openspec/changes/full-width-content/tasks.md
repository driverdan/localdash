## 1. Remove the news and events caps

- [x] 1.1 In `frontend/src/styles/news.css`, remove `max-width: 46rem` and `margin: 0 auto`
      from `#news main`, leaving its `padding: 4px 16px 24px` intact
- [x] 1.2 In `frontend/src/styles/news.css`, remove `max-width: 46rem` and `margin: 0 auto`
      from `#news .sources`, leaving its padding, font size, and color intact
- [x] 1.3 In `frontend/src/styles/events.css`, remove `max-width: 46rem` and `margin: 0 auto`
      from `#events main`, leaving its `padding: 4px 16px 24px` intact
- [x] 1.4 Confirm no other rule in either sheet reintroduces a page-width cap on the feeds

## 2. Remove the home cap

- [x] 2.1 In `frontend/src/styles/home.css`, remove `max-width: 74rem` and `margin: 0 auto`
      from `.home-scroll`, keeping `width: 100%`, the flex/scroll declarations, and the padding
- [x] 2.2 Rewrite the comment above those declarations so it describes the region as filling the
      shell column at full width, with no reference to the removed cap or centering

## 3. Verify

- [x] 3.1 Build the frontend and confirm it compiles with no CSS or Svelte warnings
- [x] 3.2 Run the stack (`docker compose up --build`) and load `/`, `/news`, and `/events` at a
      wide viewport; confirm each main content region spans the page inset only by its 16px
      padding, with no centered gutter
- [x] 3.3 Confirm each page still scrolls vertically as before and the home region still
      stretches to the full shell width (the `.home-scroll` flex-item change is the one edit
      that touches flex sizing)
- [x] 3.4 Confirm `/map` is unchanged, and that the toolbars, tab bars, cards, footers, and both
      light and dark themes render as before apart from the new width
- [x] 3.5 Grep the three sheets to confirm no `max-width` page cap, `margin: 0 auto`, or stale
      cap-describing comment remains on the home, news, or events content regions
