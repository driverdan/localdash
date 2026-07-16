## Why

LocalDash is a Chattanooga-area dashboard, but its visual identity (EPB brand blue `#0071ce`,
generic system-ui type) doesn't connect it to the city it serves. Restyling to match
chattanooga.gov's design language — its navy palette and Gabarito/Inter typography — gives the site
a recognizable civic identity, and doing it via a CSS custom-property token layer removes the raw
hex values currently repeated across all six stylesheets.

## What Changes

- Introduce a design-token layer: CSS custom properties on `:root` in `base.css` (colors, and any
  shared surface/border values) that base and all per-feature sheets consume via `var(--…)` instead
  of hard-coded hexes.
- Restyle the default (light) theme to chattanooga.gov's palette: deep navy `#004360` header with
  the existing light-text-on-colored-background structure, `#18546e` links, `#000f37` text, their
  green/red/gold accent set, pale-cyan subtle backgrounds and `#e4e5e6` borders.
- Recolor the dark theme to chattanooga.gov's own dark-mode palette (`#212529` surfaces, `#dee2e6`
  text, `#668ea0` links) expressed as token overrides under `[data-theme="dark"]`; the dark theme's
  deliberate typography/layout shifts stay.
- Adopt chattanooga.gov's typography: Gabarito for headings, Inter for body text, self-hosted via
  `@fontsource` packages (the project's first bundled webfonts — no font CDN).
- Status/on-header colors that sit on the navy get bright variants (brand green/red don't read
  against `#004360`).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `frontend-styling`: add requirements for the design-token layer (custom properties as the single
  source of shared color values, consumed by all global sheets) and self-hosted typography (bundled
  webfonts, no external font requests).
- `frontend-theming`: themes may restyle by overriding the token layer in addition to targeting
  semantic hooks; the shipped dark theme defines its palette as token overrides.

## Impact

- `frontend/src/styles/*.css` — all six sheets: `base.css` gains the `:root` token block; every
  sheet's hex values move to `var(--…)`; `theme-dark.css` sheds most color rules in favor of token
  overrides.
- `frontend/src/main.ts` + `frontend/package.json` — `@fontsource/gabarito` and `@fontsource/inter`
  dependencies and imports.
- No markup, component, backend, or API changes — the `frontend-styling` semantic-hook contract
  makes this a stylesheet-layer change.
- Verification is visual (light and dark, all four pages) plus the standard frontend checks; Docker
  rebuild required to see changes.
