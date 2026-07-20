## Context

`SiteFooter.svelte` (`frontend/src/lib/`) is a static component: one `<footer class="site-footer">`
wrapping one external link. It is rendered today as the last child of the scroll region in
`HomePage.svelte`, `NewsFeed.svelte`, and `EventsPage.svelte`. Styling lives entirely in
`.site-footer` / `.site-footer a` in `frontend/src/styles/base.css` (`flex: none`, centered, 12px,
muted link color).

The map route renders `Dashboard.svelte`:

```
#layout (display:flex; flex:1; min-height:0)
├── #sidebar   width:340px; flex:0 0 340px; overflow-y:auto; padding:12px
│   ├── <FilterPanel />
│   └── <IncidentTable />
└── <MapView />  (#map — flex:1; height:100%; Leaflet)
<DetailPanel />   (overlay, outside #layout)
```

`#sidebar` is already a scrolling block container, which is the same shape the footer relies on
elsewhere. The map pane is the viewport-locked part; the sidebar is not.

## Goals / Non-Goals

**Goals:**
- Give the map route the same open-source attribution link every other route has.
- Reuse `SiteFooter` unchanged, with zero CSS additions.
- Correct the spec's over-broad "map route has no footer" exclusion.

**Non-Goals:**
- Any bottom-anchoring, sticky, or always-visible behavior for the footer.
- Restructuring `#sidebar` into a flex column or moving its `overflow-y` onto an inner wrapper.
- Adding the footer to the map pane, the legend, or `DetailPanel`.
- Touching `timeseries.css` or `base.css`.

## Decisions

**Append `<SiteFooter />` as the last child of `#sidebar`, after `<IncidentTable />`.**
This is the smallest edit that matches the established pattern: the footer is the final element of
a scroll region. `#sidebar` is a plain block container, so the footer's `flex: none` is inert there
and `.site-footer`'s centering and padding apply unchanged against the sidebar's 340px width.

*Alternative considered — bottom-pinned strip inside a flex-column sidebar:* would read more
literally as "bottom of the sidebar", but requires restructuring `#sidebar` (flex column plus an
inner `overflow-y: auto` wrapper) and contradicts the existing "Footer is not fixed" scenario.
Rejected: more CSS, less consistency.

*Alternative considered — `margin-top: auto` on a flex-column sidebar:* sticks to the bottom when
content is short, flows when long. Rejected deliberately: it is route-specific special-casing, and
the whole point is that the map route behaves like the others with no exceptions.

**Spec change is MODIFIED, not REMOVED + ADDED.** The requirement's subject (the footer and its
placement rule) is unchanged; only its route coverage is. The "Map route has no footer" scenario is
replaced in place by scenarios describing the sidebar placement, plus one asserting the footer does
not appear over the map pane — the accurate residue of the old exclusion.

**`SiteFooter.svelte`'s leading comment must be updated.** It currently reads "(home, news,
events — never the viewport-locked map)", which becomes false. The comment is the component's only
documentation of the placement rule, so leaving it stale would be the change's most likely source
of future confusion.

## Risks / Trade-offs

- **Footer is buried under a long incident list on a busy day** → Accepted, and explicitly the
  requested behavior. It is the same trade-off already accepted on the news and events routes.
- **Footer floats mid-sidebar with empty space beneath it when few incidents are active** →
  Accepted; captured as a scenario so it is not later "fixed" as a bug.
- **Sidebar padding (12px) plus `.site-footer` padding (20px top) stack** → Cosmetic only, and
  consistent with how the footer already sits inside padded content regions elsewhere. No CSS
  override; verify visually rather than pre-emptively adjusting.
