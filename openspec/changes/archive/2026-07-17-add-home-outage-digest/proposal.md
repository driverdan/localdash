## Why

Power and fiber outages are the most actionable at-a-glance signal LocalDash collects, but
today they are only visible by opening `/map` and looking for markers. The home page's widget
digest — news, weather, events — has no utility-status widget, even though the EPB collector
already polls both services and the timeseries API already serves the current active set. The
home grid was explicitly designed for this ("future widgets (timeseries summary) are added as
pure additions").

## What Changes

- Add an "Outages" digest widget to the home page, in the right widget column directly beneath
  the weather strip and above the events widget.
- Content: one row per EPB service with active outages — count plus summed customers affected
  (e.g. "3 power outages · 1,240 customers"; "1 fiber outage · 89 customers") — and a
  reassuring "No current outages" zero state. A "View all →" link navigates client-side to
  `/map`.
- Data path: frontend-computed from the existing `GET /api/v1/timeseries/entities?source=epb`
  endpoint (active-only by default; features carry `category` `energy`|`fiber` and
  `customer_quantity`). **No new backend endpoint.**
- Live updates: a permanent subscription to the existing `timeseries` WS topic refetches the
  digest when a diff's `source` is `epb`; the loader also joins the home reconnect refetch
  list. This makes the home feature the first *permanent* subscriber to the `timeseries`
  topic (previously route-scoped to the map).
- The widget is always shown — it does not consult source admin state; with no active
  outages (for any reason) it renders the zero state.
- Scope: EPB only. TN American Water advisories stay out; the widget name "Outages" leaves
  that door open.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `frontend-home`: the widget-grid requirement's right column gains the outages widget between
  weather and events; a new outages digest widget requirement; the live-refresh requirement
  gains the `timeseries`-topic (epb-filtered) subscription and reconnect refetch.
- `frontend-live`: the permanent-subscriptions requirement no longer characterizes the
  `timeseries` topic as exclusively route-scoped — home holds a permanent, source-filtered
  subscription alongside the map's mount-scoped one.

## Impact

- `frontend/src/features/home/api.ts` — outage digest loader + types (fetches the epb
  entities and reduces them to the summary).
- `frontend/src/features/home/state.svelte.ts` — outage digest state + loaded/error flags.
- `frontend/src/features/home/components/OutageDigest.svelte` — new widget component.
- `frontend/src/features/home/components/HomePage.svelte` — mount the widget in the column.
- `frontend/src/features/home/live.ts` — `timeseries` subscription (filtered to `epb`) +
  reconnect entry.
- `frontend/src/styles/home.css` — widget styling per the global styling contract.
- `openspec/specs/frontend-home/spec.md`, `openspec/specs/frontend-live/spec.md` — updated
  requirements.
- No backend, schema, or config changes.
