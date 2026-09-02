## Context

The app shell (`#app`) is a full-height flex column: a `flex: none` header, then the active
route's region as a `flex: 1` child. Each route region already spans the viewport width and owns
its own vertical scroll. The width constraint lives one level deeper, on the content inside those
regions:

```
/map      #layout ── flex row ──────────────────────── full width today
          ├── #sidebar  340px
          └── #map      flex: 1

/         .home-scroll ── flex:1 column, IS the scroll container
          width:100%; max-width:74rem; margin:0 auto     ← cap here
          └── .home-grid  auto-fit minmax(20rem, 1fr)

/news     #news ── flex:1, IS the scroll container, full width
          ├── .toolbar   full width, justify-content:center
          ├── .tabs      full width, justify-content:center
          ├── main       max-width:46rem; margin:0 auto  ← cap here
          ├── .sources   max-width:46rem; margin:0 auto  ← cap here
          └── .site-footer

/events   #events ── same shape as #news
          ├── .toolbar / .tags   full width
          ├── main       max-width:46rem; margin:0 auto  ← cap here
          └── .site-footer
```

Two different centering mechanisms are in play. `#news main`, `#news .sources`, and
`#events main` are ordinary block elements inside a block container, so `margin: 0 auto`
centers them in the normal way. `.home-scroll` is a *flex item* in the shell column; its
`margin: 0 auto` centers it on the cross axis, which is also why it carries an explicit
`width: 100%` — cross-axis auto margins suppress a flex item's default `stretch`, so without
that declaration the region would shrink to its content. The existing comment at
`home.css:20-23` documents exactly this.

Per the styling contract (`frontend-styling`), all of this lives in the global per-feature
stylesheets; no component carries scoped visual styles. So the change is confined to CSS.

## Goals / Non-Goals

**Goals:**
- The main content region of `/`, `/news`, and `/events` fills the page width, matching `/map`.
- Leave every other visual property untouched: padding, backgrounds, card styling, spacing,
  toolbars, grid track definitions.
- Leave no dead declarations or stale comments behind describing a cap that no longer exists.

**Non-Goals:**
- Reflowing the news/events feeds into a multi-column card grid. The cards stay a single
  full-width column.
- Preserving a reading measure by capping the cards themselves instead of their container.
- Changing horizontal padding, adding responsive breakpoints, or introducing a
  "full-bleed vs. padded" token.
- Touching `/map`, the header, the site footer, or the debug overlay.
- Restructuring `.home-grid`'s children so `auto-fit` yields more than two tracks.

## Decisions

**Remove the caps at the container, not at the card.** The alternative — keeping the region
full width but giving `.story-card` / `.event-card` their own `max-width` — would preserve
reading measure but produce a left-hugging column with a large void on the right, which reads
worse than the centered layout it replaces. The user's intent is that the content itself spans
the page, so the cap comes off the container and nothing is reintroduced downstream.

**Delete the now-inert `margin: 0 auto` alongside each `max-width`, rather than only the
`max-width`.** Deleting just the cap would work — with no free space, `auto` margins resolve to
zero — but it leaves a centering declaration that does nothing and a comment describing a
constraint that is gone. Removing both keeps the stylesheets readable as the "single source of
visual truth" the contract calls for.

**For `.home-scroll`, keep `width: 100%` and update its comment.** Once the auto margins are
gone the flex item stretches on its own, so the declaration becomes redundant — but it is
harmless, and keeping it makes the region's full-width intent explicit at the point of use. The
three-line comment above it currently explains the cap-and-center trio and must be rewritten;
leaving it would actively mislead the next reader.

**Keep the toolbars centered.** `#news .toolbar`, `#news .tabs`, `#events .toolbar`, and
`#events .tags` are already full width with `justify-content: center`, so they need no edit.
The controls will now sit centered above a full-width feed rather than above a centered one.
That is a real visual shift, and left-aligning them to match the feed's new left edge was
considered and rejected: it is a separate design decision, outside "remove the cap, keep
everything else the same."

**No spec change to the per-feature capabilities.** `frontend-home`, `frontend-news`, and
`frontend-events` never stated a content width, so none of their requirements change. The new
requirement goes in `frontend-styling`, which already owns cross-feature layout contracts.

## Risks / Trade-offs

- **Reading measure is lost on the feeds.** At 1920px a story headline and summary run to
  ~250 characters per line, well past the 45–90 character readability range. → Accepted
  deliberately and recorded in the proposal; the fix, if wanted later, is a card grid, which
  is a follow-up change rather than a revert.
- **`.home-grid` gains width but not columns.** It has exactly two top-level children (the news
  widget and `.widget-column`), and `auto-fit` collapses the empty tracks, so uncapping yields
  two ~950px columns rather than more widgets per row. → Expected, not a defect; splitting
  `.widget-column` into separate grid items is explicitly a non-goal here.
- **Story and event card images stretch.** `.image img` is `width: 100%` with
  `max-height: 260px` and `object-fit: cover`, so a wider card crops the same source image
  harder vertically. → Visual only, and the cover fit means no distortion; verified during
  review rather than mitigated in code.
- **16px side padding at very wide viewports.** The content will sit 16px from each edge, which
  can read as unfinished on a 4K display. → Out of scope by instruction; noted so a future
  change can revisit it as a deliberate padding decision.
- **Regression risk is low but real:** `.home-scroll` losing its auto margins is the only edit
  that interacts with flex sizing. → Verify the home region still stretches full width and its
  vertical scroll still works after the edit.
