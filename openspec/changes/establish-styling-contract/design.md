# Design: establish-styling-contract

## Context

Svelte scopes a component's `<style>` block by compiling `.toolbar { }` to `.toolbar.svelte-hash`
and stamping `svelte-hash` onto the element. This is great for encapsulation and fatal for external
theming: a theme stylesheet targeting `.toolbar` collides at equal specificity with a hash it
cannot predict or control. The map/timeseries feature sidesteps this entirely — it has no scoped
styles; everything is global `app.css` on semantic hooks. News and events took the scoped path
(six components, ~234 lines, zero `:global()` escapes). The goal is one consistent, themeable
model; the map already proves it works in this codebase without style collisions.

## Goals / Non-Goals

**Goals:**

- A written styling contract every feature follows, with the map feature as the reference.
- News/events migrated onto it: global stylesheets, semantic markup hooks, no scoped visual styles.
- Markup that a future theme can restyle in layout, typography, and color — not just color.
- Rendered output visually identical before and after (pure refactor).

**Non-Goals:**

- No theme, theme switcher, `data-theme`, or persistence (that is `add-theme-switcher`).
- No visual redesign — no intended pixel changes.
- No change to the map/timeseries feature's behavior; it is the reference, not the subject.
- No CSS framework or preprocessor adoption; plain global CSS as today.

## Decisions

### 1. Un-scope news/events to the global model (not `:global()` everywhere)

The two ways to make scoped components themeable are (a) delete the scoping and move styles to
global sheets, or (b) wrap every rule in `:global()`. Option (b) keeps the styles physically in the
component but defeats the purpose — it is scoping-shaped boilerplate that still couples visual style
to component files. Option (a) matches what the map already does and yields a real single source of
visual truth. We take (a): the six components become markup (plus behavior), and their styles move
to global feature stylesheets.

Trade accepted: we lose Svelte's automatic collision protection and rely on naming discipline
instead. The map sustains exactly this today without collisions, so the risk is demonstrated-low;
semantic, feature-namespaced class names (e.g. `.story-card`, `.event-card`) keep it manageable.

### 2. Global CSS structure: a base layer plus per-feature sheets

`app.css` is currently one 96-line file already doing double duty (reset + shell + map). Reorganize
into a small, explicit structure so the "one source of visual truth" stays navigable and so a theme
knows what surface it is overriding:

```
frontend/src/styles/
  base.css      reset, element defaults, shell chrome (header, status bar, layout regions)
  timeseries.css  map/filters/table/detail/legend (lifted from today's app.css)
  news.css      lifted from the 5 news components
  events.css    lifted from the 2 events components
```

Exact filenames are an implementation detail for tasks; the requirement is: base + per-feature,
imported once at the app root, no scoped visual styles in components. This keeps feature isolation
(the shell's import rules already forbid cross-feature imports; per-feature sheets mirror that).

### 3. The markup contract: semantic hooks, no presentational scaffolding

For CSS to change *layout* (not just color), the markup must be an assumption-free semantic
substrate — the CSS Zen Garden principle:

- **Singleton regions → ids**: the shell/header, sidebar, map, and each page's root region carry a
  stable id (the map already has `#layout`, `#sidebar`, `#map`, `#incident-table`).
- **Repeated elements → semantic classes**: `.story-card`, `.event-card`, `.tab-bar`/`.tabs`,
  `.chip`, `.toolbar`, `.filter-group`, etc. — named for *what they are*, not how they look.
- **State → classes or `data-*`**: active/closed/selected expressed as `.is-active` /
  `[data-state]`, targetable by a theme.
- **No presentational-only wrappers, no structural inline styles**: e.g. a story list is a flat set
  of `.story-card`s a theme can `grid` or stack, not pre-nested in fixed column divs. Data-driven
  inline values stay (the map's `style="background:{catColor}"` on a category dot, EPB marker
  sizing) — those are data, not presentation.

### 4. Verify by pixel parity, not by reading CSS

Because this is a pure refactor, the check that matters is that the app looks the same. Verification
drives the running app across all three pages (map, news, events) before and after and compares —
the styles moved, the output did not. This is the one place regressions would hide (a lifted rule
losing specificity, a dropped scoped selector), so it is the explicit verification gate.

## Risks / Trade-offs

- [Lifting a scoped rule to global changes its specificity or leaks to another feature] → keep
  rules feature-namespaced under their semantic hooks; verify by pixel parity per page, not just
  "it compiles."
- [Losing Svelte scoping invites future style leakage] → naming discipline + per-feature sheets;
  the map demonstrates this holds here. Accepted as the cost of themeable markup.
- [Markup normalization accidentally changes layout] → treat markup edits as behavior-preserving;
  any intended structural change to enable theming must still render identically under today's
  styles.
- [Scope creep into a redesign] → explicit non-goal; pixels held constant, reviewed as such.

## Open Questions

None blocking. Exact stylesheet filenames and whether state uses `.is-*` vs `data-*` are
implementation choices for tasks, guided by the contract above.
