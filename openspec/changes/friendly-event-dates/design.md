## Context

`EventCard.svelte` builds its `when` line from `fmt(item.starts_at)` — a thin wrapper around
`new Date(iso).toLocaleString()` — plus `toLocaleTimeString()` for the end time. The result
(`7/18/2026, 7:00:00 PM – 9:00:00 PM`) is hard to scan and includes seconds. The card is the
only place event dates render; both the `/events` page and the home page's upcoming-events
widget use it. `starts_at`/`ends_at` arrive as timezone-aware ISO strings, so `new Date()`
yields the correct instant and local-day math is safe.

## Goals / Non-Goals

**Goals:**
- Natural-language start dates: `Today`, `Tomorrow`, weekday name for 2–6 days out, formatted
  date for 7+ days out (year shown only when it differs from the current year)
- Seconds-free times, end time appended when present: `Today · 7:00 PM – 9:00 PM`

**Non-Goals:**
- No staleness handling: labels recompute only on normal re-render. The events feature already
  auto-reloads every 5 minutes, which refreshes them in practice.
- No change to `fmt()` or the timeseries feature's timestamp display, where relative-day
  language would be wrong.
- No locale-specific "Today"/"Tomorrow" wording (plain English strings; the app is
  English-only).
- No backend or API changes.

## Decisions

- **One helper, whole line**: `fmtEventDate(startsAt: string, endsAt: string | null): string`
  in `frontend/src/lib/format.ts` returns the complete `when` string. Keeping composition out
  of the component means the card's `$derived` becomes a single call, and the formatting rules
  live next to the other formatters. Alternative — a date-only helper with the card composing
  times — spreads the logic across two files for no benefit.
- **Calendar-day diff, not 24-hour intervals**: "Today" means the same local calendar day.
  Compute the difference in days between local midnights of `now` and `starts_at`. An event at
  11 PM tonight is `Today` even if it is 20 hours away; an event at 8 AM tomorrow is `Tomorrow`
  even if it is 10 hours away.
- **Weekday-name window is 2–6 days**: a bare weekday name is only unambiguous for the next
  six days. Seven days out shares today's weekday, so `Thursday` would read as *today*; day 7
  and beyond get the formatted date.
- **`Intl.DateTimeFormat` for names and dates**: weekday names via `{ weekday: "long" }`,
  far dates via `{ weekday: "short", month: "short", day: "numeric" }` (plus `year: "numeric"`
  when the event's local year differs from the current year). Times via
  `{ hour: "numeric", minute: "2-digit" }`. No new dependencies.
- **`·` separator between date and time**, matching the card's existing `·` usage in the
  venue/address line; the en dash `–` between start and end times is kept.
- **Past events fall through to the date format**: anything before today's local midnight
  (possible only transiently, since the API filters to upcoming) renders as a formatted date
  rather than gaining "Yesterday"-style labels.

## Risks / Trade-offs

- [Label can go stale on a long-lived page] → Accepted per proposal; the feature's 5-minute
  auto-reload re-renders the list, bounding staleness to ~5 minutes after midnight.
- [No frontend unit-test runner exists (`svelte-check` only)] → The helper is written as a
  pure function taking ISO strings, so verification is `svelte-check` plus visual inspection
  of cards spanning today/tomorrow/this-week/far-future; a test runner is out of scope.
- [Locales other than English would get mixed-language output] → Accepted; the app's UI is
  English-only and `Intl` pieces still follow the browser locale for date/time shapes.
