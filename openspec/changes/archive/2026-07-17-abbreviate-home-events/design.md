## Context

The home page (`frontend/src/features/home/`) renders an "Upcoming events" widget that reuses
the events feature's full `EventCard` inside a `#events`-id'd widget body, purely so the events
feature's global CSS applies. `home.css` neutralizes the page-frame rules that ride along with
that id and trims the card image height. The result is five full-fat cards (tags, image, title,
venue, description, source links) in a digest slot.

The events data is already sufficient: `loadEvents()` in `home/api.ts` fetches full
`EventItem`s, and `fmtEventDate(starts_at, ends_at)` in `lib/format.ts` is a shared lib
producing the same formatted date/time string the events page shows. The primary link target is
`item.links[0]?.source_url`, the same choice `EventCard` makes for its title.

`WeatherStrip` already establishes the precedent of a home-owned widget rendering styled in
`home.css`.

## Goals / Non-Goals

**Goals:**
- Abbreviate the home events digest to: linked title, full formatted date/time, distance.
- Keep `EventCard` and the events page untouched.
- Keep data flow (fetch, state, live refetch, error/empty handling) unchanged.

**Non-Goals:**
- No change to the news widget's `StoryCard` reuse.
- No new API shape, no digest-specific endpoint.
- No change to how the events page itself renders.

## Decisions

**Home-owned digest component over a `compact` EventCard prop or CSS-only hiding.**
A new `EventDigest.svelte` in `features/home/components/` renders one compact row per event.
CSS-only hiding was rejected as fragile (distance shares a `.meta` row with tag badges, so
selectors get fiddly) and wasteful (hidden `<img>` still in the DOM). A `compact` prop was
rejected because the two renderings share almost nothing visually, so "reuse" buys only the
one-line `links[0]` link choice while bifurcating an otherwise clean card. The digest follows
the `WeatherStrip` precedent: home owns the rendering, `home.css` owns the styling.

**Props: the digest takes the full `EventItem`.** Home already holds `EventItem[]` in state;
the component derives its display strings itself (`fmtEventDate(item.starts_at, item.ends_at)`
from the shared lib, `item.distance_miles`, `item.links[0]?.source_url`). No mapping layer.

**Full date/time string, not start-only.** The digest shows the same
`fmtEventDate(starts_at, ends_at)` output as the events page (including end times/ranges), per
the explicit product decision. Distance renders after it (e.g. `· 3.2 mi`) only when
`distance_miles` is non-null. Events without a link render the title as plain text, matching
`EventCard`'s effective behavior (`links[0]?.source_url` yields no href).

**Drop the `#events` scoping from the widget body.** The digest no longer inherits events-page
CSS, so the widget body loses the `#events` id, and `home.css` drops the `.widget #events`
neutralization and the `.widget #events .event-card .image img` trim rule (the `.widget #news`
halves stay). New `.event-digest` (row) rules live in `home.css` using theme variables, per the
styling contract. The header comment in `home.css` is updated: card reuse applies where the
digest is the full card (news); home owns compact renderings otherwise (weather, events).

**Events public surface: keep `EventCard` exported.** Home stops importing it, but removing
the export is an events-feature decision with no functional payoff; the export comment is
updated (or the export dropped) only if nothing imports it — verify at implementation time and
prefer dropping the now-dead export plus its comment, since the public surface should reflect
actual consumers. Home continues importing only `EventItem` (a type) from `features/events`,
which still satisfies the public-surface import rule.

## Risks / Trade-offs

- [Divergence: future event-card improvements won't reach the digest] → Accepted; the digest
  is intentionally minimal (three data points), so there is little to diverge.
- [Duplicated `links[0]` primary-link choice in two components] → Trivial today; if a real
  primary-link policy emerges, promote it to a helper on the events public surface.
- [Long titles + long date ranges may wrap awkwardly in the narrow right column] → Style rows
  to allow wrapping (no truncation of the title link); date/distance line is short by nature.
