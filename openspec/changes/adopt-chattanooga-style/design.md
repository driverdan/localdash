## Context

LocalDash's six global stylesheets (`base.css`, four feature sheets, `theme-dark.css`) hard-code
every color — ~34 distinct hex/rgba values in the light sheets alone, with the EPB blue `#0071ce`
repeated 19 times. The site should instead match chattanooga.gov's design language. Its real
tokens were mined from the live site's theme CSS (Drupal + Bootstrap):

- Primary navy `#004360` (`--bs-primary`, banners, active tabs); button navy `#004c93`
- Links `#18546e` (light) / `#668ea0` (dark); body text `#000f37`
- Accents: green `#00874e`, red `#b60000`, amber `#b35f00`, gold `#ffb949`, cyan `#00a6cb`
- Subtle backgrounds `#e6f6fa` (pale cyan), `#ccd9df`; borders `#e4e5e6`
- Dark mode: body `#212529`, text `#dee2e6`, borders in the `#495057` grey band with navy-subtle
  accents (`#00283a`)
- Type: Gabarito ("highlight" face — headings), Inter (body), Arial fallback

Decisions already made with the user: keep the current header structure (light text on a colored
background — navy replaces EPB blue; NOT chattanooga.gov's white header), recolor the dark theme to
their dark palette, introduce a custom-property token layer, and bundle both fonts.

## Goals / Non-Goals

**Goals:**

- Default (light) theme reads as chattanooga.gov's palette and typography.
- Dark theme recolored to chattanooga.gov's dark-mode palette; its typography/layout shifts stay.
- One `:root` token block in `base.css` is the single source of shared color values; all sheets
  consume `var(--…)`; `[data-theme="dark"]` overrides tokens instead of restating colors.
- Fonts self-hosted through the Vite bundle — zero external font requests.

**Non-Goals:**

- No markup or component changes (the semantic-hook contract makes this stylesheet-only).
- Not replicating chattanooga.gov's layout (white header, megamenu, hero banner, Bootstrap card
  grids) — palette + typography only, current density and structure kept.
- No new theme registry entry — this restyles the existing `light` default and `dark` theme.
- No pixel-for-pixel fidelity target; "recognizably the same design language" is the bar.

## Decisions

### 1. Token granularity: a core semantic set, not one token per hex

~20 semantic tokens (indicative names/values; exact set finalized in implementation):

| Token | Light | Dark |
| --- | --- | --- |
| `--color-primary` | `#004360` | `#004360` (usage-dependent brightening where needed) |
| `--color-primary-strong` | `#004c93` | — |
| `--color-link` | `#18546e` | `#668ea0` |
| `--color-text` | `#000f37` | `#dee2e6` |
| `--color-text-muted` | slate (from `#5a6573` band, navy-tinted) | `#adb5bd` band |
| `--color-page-bg` / `--color-panel-bg` / `--color-surface-subtle` | `#fff` / `#fff` / `#e6f6fa`-`#f5f5f5` band | `#212529` / `#2b3035` / `#343a40` band |
| `--color-border` / `--color-border-soft` | `#e4e5e6` + softer variant | `#495057` band |
| `--color-ok` / `--color-err` / `--color-warn` | `#00874e` / `#b60000` / `#b35f00` | brightened variants |
| `--color-on-primary` / `--color-ok-on-primary` / `--color-err-on-primary` | `#fff` / bright green (`#34cf59` family) / light red | same |
| `--font-body` / `--font-heading` | Inter / Gabarito stacks | same |

The current sheets' near-duplicate greys (`#dde2e8`, `#e6eaef`, `#eef2f6`, `#f4f6f9`, …) collapse
into the nearest token. That is a deliberate normalization — a visual change is happening anyway,
and per-hex tokens would just relocate the mess. Truly local one-offs (e.g. map category colors
fed inline from data) stay as they are per the styling contract.

Alternative rejected: adopting chattanooga.gov's own variable names (`--btn-bg-color`,
`--layer-bg-dark`). Their names encode their Drupal component structure, not ours.

### 2. Dark theme = token overrides + kept structure

`[data-theme="dark"]` gets one block overriding the token values (right column above). Rules in
`theme-dark.css` that only restated colors are deleted; rules that change typography or layout
(heading weight/tracking, etc.) remain, preserving the theming spec's "more than color" property.
The dark basemap tile override in the theme registry is untouched. Expected outcome:
`theme-dark.css` shrinks from ~300 lines to roughly a third of that.

### 3. Fonts via `@fontsource`, imported in `main.ts`

`@fontsource/gabarito` + `@fontsource/inter`, importing only needed weights (Inter 400/600/700,
Gabarito 500/700) before the stylesheets in `main.ts` so Vite bundles and hashes the woff2 files.
Body stays 14px for dashboard density, now in Inter; `h1`/`h2` and other heading-class hooks take
`--font-heading`. System-ui remains in the stacks as fallback; the existing monospace stacks are
untouched.

Alternatives rejected: Google Fonts CDN (external dependency contradicts a local dashboard;
blocked offline) and hand-vendored woff2 + `@font-face` (more upkeep than the versioned packages).

### 4. On-primary status colors are their own tokens

The header status bar sits on `#004360`; brand green `#00874e` / red `#b60000` fail contrast
there. Anything rendered on the navy uses the `-on-primary` tokens (bright `#34cf59`-family green,
light red — like today's `#6ee7a8`/`#ff9a9a`), keeping the darker brand accents for use on light
surfaces.

## Risks / Trade-offs

- [Grey normalization subtly shifts non-brand surfaces] → Intended; verify visually page-by-page
  (home, map, news, events) in both themes rather than aiming for before/after pixel equality.
- [Navy `#004360` is darker than the current blue; low-opacity white overlays (nav active state,
  theme switcher) render differently] → Re-check those overlay alphas on the new header during
  visual review.
- [First webfonts add ~100 KB and can FOUC] → Only 5 weight files, bundled locally (no network
  round-trip beyond the app's own origin); accept default `font-display` swap behavior.
- [Chattanooga dark-mode values are Bootstrap-derived and may pair oddly with our panel structure]
  → The `#2b3035`/`#343a40` panel/raised split mirrors the current dark theme's three-surface
  system, so the structure carries over; adjust within the grey band during review if murky.
- [chattanooga.gov redesigns later] → Tokens make any future re-palette a one-block edit.

## Migration Plan

Single PR, stylesheet-layer only; rollback is reverting it. No data, API, or markup migration.
Docker rebuild (`sg docker -c 'docker compose up --build'`) to verify, per project practice.

## Open Questions

None — palette source, header treatment, dark strategy, token layer, and font delivery are all
decided. Exact hex choices within the named color bands are implementation-time judgment calls
resolved during visual review.
