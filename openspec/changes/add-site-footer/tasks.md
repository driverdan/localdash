# Tasks: Add Site Footer

## 1. Footer component

- [ ] 1.1 Create `frontend/src/lib/SiteFooter.svelte`: a semantic `<footer class="site-footer">`
      with one link — text "100% Open Source" → `https://github.com/driverdan/localdash`,
      `target="_blank" rel="noopener"`. No props, no state.
- [ ] 1.2 Add `.site-footer` styles to `frontend/src/styles/base.css` beside the shell rules:
      centered small muted text (`--color-text-muted`), modest padding, tokens only (no
      `theme-dark.css` changes).

## 2. Render sites

- [ ] 2.1 Render `SiteFooter` as the last child of the home scroll region (`.home-scroll` in the
      home feature's page component).
- [ ] 2.2 Render `SiteFooter` as the last child of the news scroll region (`#news`), after the
      existing sources/feed-health footer.
- [ ] 2.3 Render `SiteFooter` as the last child of the events scroll region (`#events`).

## 3. Verify

- [ ] 3.1 `cd frontend && npm run check` passes with 0 errors and `npm run build` succeeds.
- [ ] 3.2 Rebuild and run the stack (`sg docker -c 'docker compose up --build'`); confirm the
      footer appears after the content when scrolling to the bottom of `/`, `/news`, and
      `/events`, is not pinned to the viewport, opens the repo in a new tab, and does not
      appear on `/map`. Check dark theme renders it legibly.
