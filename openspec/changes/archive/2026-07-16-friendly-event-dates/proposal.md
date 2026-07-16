## Why

Event cards show start times as raw `toLocaleString()` output (e.g. `7/18/2026, 7:00:00 PM`):
a numeric date, seconds nobody needs, and no sense of how soon the event is. Natural-language
dates ("Today", "Tomorrow", "Saturday") make the events list scannable at a glance.

## What Changes

- Event cards render the start date as natural language relative to the viewer's local day:
  - same day → `Today`
  - next day → `Tomorrow`
  - 2–6 days out → weekday name (e.g. `Saturday`)
  - 7+ days out → a formatted date (e.g. `Sat, Jul 25`), including the year only when it
    differs from the current year
- Times render without seconds (e.g. `7:00 PM`), with the end time appended when present:
  `Today · 7:00 PM – 9:00 PM`
- A new `fmtEventDate()` helper is added to `frontend/src/lib/format.ts`; the existing `fmt()`
  is untouched (the timeseries feature uses it for observation timestamps, where relative-day
  language would be wrong)
- No staleness handling: labels recompute only on normal re-render (the feature's existing
  5-minute auto-reload refreshes them in practice)

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `frontend-events`: the event card's "start time (and end time when present)" display becomes
  a natural-language date plus seconds-free times, per the rules above. The home page's upcoming
  events widget reuses `EventCard` and inherits the change; `frontend-home` requirements are
  unchanged.

## Impact

- `frontend/src/lib/format.ts` — new `fmtEventDate()` helper
- `frontend/src/features/events/components/EventCard.svelte` — uses the new helper for the
  `when` line
- No backend, API, or dependency changes; `starts_at`/`ends_at` are already timezone-aware
  ISO strings
