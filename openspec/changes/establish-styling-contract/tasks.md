# Tasks: establish-styling-contract

## 1. Global stylesheet structure

- [x] 1.1 Create `frontend/src/styles/` with a `base.css` (reset, element defaults, shell chrome:
      header, status bar, layout regions) and a `timeseries.css`, moving the existing `app.css`
      rules into them unchanged; import the sheets once at the app root (replacing the `app.css`
      import) and confirm the map page is pixel-identical
- [x] 1.2 Document the styling contract (semantic hooks, global feature sheets, no scoped visual
      styles, assumption-free markup) as a short comment/header in `base.css` or a `styles/README`,
      with the map feature named as the reference implementation

## 2. Migrate the news feature

- [x] 2.1 Create `frontend/src/styles/news.css`; move the styles out of `NewsFeed`, `CategoryTabs`,
      `StoryCard`, and `SourcesFooter` into it, keeping selectors on the components' semantic hooks
- [x] 2.2 Normalize the news markup: ensure story cards, tabs, chips, and the sources footer expose
      semantic classes and express active/closed state via class or `data-*`; remove any
      presentational-only wrappers or structural inline styles
- [x] 2.3 Delete the now-empty `<style>` blocks from the four news components and verify the news
      page renders pixel-identically (feed, All grouped view, a category tab, sources footer)

## 3. Migrate the events feature

- [x] 3.1 Create `frontend/src/styles/events.css`; move the styles out of `EventsPage` and
      `EventCard` into it, keeping selectors on the components' semantic hooks
- [x] 3.2 Normalize the events markup: ensure the toolbar, topic chips, and event cards expose
      semantic classes and express active state via class or `data-*`; remove any
      presentational-only wrappers or structural inline styles
- [x] 3.3 Delete the now-empty `<style>` blocks from the two events components and verify the events
      page renders pixel-identically (toolbar, active chip, event list)

## 4. Verification

- [x] 4.1 Run `npm run check` in `frontend/` (0 errors) and rebuild via
      `sg docker -c 'docker compose up --build -d'`
- [x] 4.2 Confirm no feature component retains a scoped visual `<style>` block
      (`grep -rL` clean across `features/`), and that all three pages (map, news, events) render
      visually identically to before this change
