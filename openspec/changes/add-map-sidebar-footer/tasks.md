## 1. Render the footer in the map sidebar

- [ ] 1.1 In `frontend/src/features/timeseries/components/Dashboard.svelte`, import `SiteFooter`
      from `../../../lib/SiteFooter.svelte` (matching the import style used by `HomePage`,
      `NewsFeed`, and `EventsPage`)
- [ ] 1.2 Render `<SiteFooter />` as the last child of `<aside id="sidebar">`, immediately after
      `<IncidentTable />` — no wrapper element, no class, no inline style
- [ ] 1.3 Confirm no changes are made to `frontend/src/styles/timeseries.css` (`#sidebar`) or
      `frontend/src/styles/base.css` (`.site-footer`)

## 2. Keep documentation accurate

- [ ] 2.1 Update the leading comment in `frontend/src/lib/SiteFooter.svelte` so it no longer says
      the map is excluded — state that it is the last child of each route's scroll region,
      including the map route's sidebar

## 3. Verify

- [ ] 3.1 Run `npm run check` in `frontend/` and confirm svelte-check passes with no new errors
- [ ] 3.2 Run `npm run format` in `frontend/` so the edited files match Prettier output
- [ ] 3.3 Rebuild and run the app (`docker compose up --build`), visit `/map`, scroll the sidebar
      to the bottom, and confirm the "100% Open Source" link appears after the incident table and
      opens the repo in a new tab
- [ ] 3.4 With few active incidents (short sidebar), confirm the footer sits directly after the
      table with empty space below rather than pinned to the sidebar's bottom edge
- [ ] 3.5 Confirm the map pane, legend, and detail panel are visually unchanged, and that the
      home, news, and events footers still render as before
