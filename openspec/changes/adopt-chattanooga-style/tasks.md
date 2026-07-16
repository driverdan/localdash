## 1. Fonts

- [ ] 1.1 Add `@fontsource/gabarito` and `@fontsource/inter` to `frontend/package.json` and import
  the needed weights (Inter 400/600/700, Gabarito 500/700) in `main.ts` before the stylesheets
- [ ] 1.2 Verify the built bundle serves woff2 from the app's own origin with no external font
  requests (network tab / grep of dist)

## 2. Token layer

- [ ] 2.1 Add the `:root` design-token block to `base.css`: Chattanooga light palette (primary
  `#004360`, primary-strong `#004c93`, link `#18546e`, text `#000f37`, muted/border/surface bands,
  ok/err/warn accents, on-primary variants) and `--font-body` / `--font-heading` stacks
- [ ] 2.2 Convert `base.css` rules to consume tokens (header navy + light text, nav, status bar
  on-primary colors, headings in `--font-heading`, body in `--font-body`, tables, debug overlay)
- [ ] 2.3 Convert `timeseries.css` to tokens, collapsing near-duplicate greys into the nearest
  token (data-driven inline map colors stay)
- [ ] 2.4 Convert `news.css` to tokens
- [ ] 2.5 Convert `events.css` to tokens
- [ ] 2.6 Convert `home.css` to tokens
- [ ] 2.7 Confirm no token-covered raw hex remains outside token definitions (grep the sheets)

## 3. Dark theme recolor

- [ ] 3.1 Replace `theme-dark.css` color rules with a `[data-theme="dark"]` token-override block
  using chattanooga.gov's dark palette (`#212529` page, `#2b3035`/`#343a40` panels, `#dee2e6` text,
  `#668ea0` links, `#495057`-band borders, brightened accents)
- [ ] 3.2 Keep (and re-verify) the dark theme's typography/layout rules and the dark basemap
  override; delete now-redundant per-element color rules

## 4. Visual verification and checks

- [ ] 4.1 Rebuild via Docker and review all four pages (home, map, news, events) in light and dark:
  header contrast, nav active/hover overlays on navy, status-bar ok/err legibility, cards, tabs,
  tables, detail/filter panels, debug modal
- [ ] 4.2 Run the frontend checks used by the project (format/lint/svelte-check) and fix fallout
