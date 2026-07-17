## Context

The EPB collector already polls power (`energy`) and fiber outages into the timeseries entity
store; `GET /api/v1/timeseries/entities?source=epb` returns the currently active set as GeoJSON
(each feature carrying `category`, `status`, `customer_quantity`), and every ingest cycle
broadcasts a `{topic: "timeseries", type: "diff", source: "epb", ...}` WS message. The home
page composes digest widgets that fetch on mount, follow their feature's live signal, and
refetch on reconnect. The right widget column (`widget-column` in `HomePage.svelte`) was built
so new widgets are pure additions.

This change is frontend-only: a new digest widget that reads existing APIs.

## Goals / Non-Goals

**Goals:**
- An at-a-glance outage summary (counts + customers affected per service) beneath the weather
  strip, live-updating with the same latency as the map.
- Zero backend changes.
- Always present, with a reassuring "No current outages" state when quiet.

**Non-Goals:**
- TN American Water advisories (different vocabulary — polygons, advisory text; the widget name
  "Outages" leaves room to fold them in later as their own change).
- Status-level detail (crews en route etc.) or per-outage rows; this is a two-line summary.
- A dedicated summary endpoint — client-side aggregation over the tiny active set is enough.
- Map deep-linking pre-filtered to EPB (the map has no such URL contract today).
- Reflecting source admin state: the widget never consults `/timeseries/sources` or other
  configuration — it is unconditionally rendered, and an empty active set is simply the
  zero state.

## Decisions

### Frontend-computed summary from the existing entities endpoint
The digest fetches `/api/v1/timeseries/entities?source=epb` and reduces features to
`{energy: {count, customers}, fiber: {count, customers}}`. This mirrors how the news/events
digests reuse their feature endpoints with parameters rather than adding home-specific APIs.
The active outage set is small (typically zero to tens of features), so payload size and
client work are negligible. `customer_quantity` values that are missing or non-positive are
treated as zero; a service whose sum is zero renders its count without a customers fragment.

*Alternative considered:* a `/timeseries/summary` endpoint. Rejected — new API surface with a
single consumer, and it would duplicate aggregation the client can do trivially.

### Always rendered; no dependence on source configuration
The widget renders unconditionally — it never consults `/timeseries/sources` or any other
admin/config state. An empty active set shows the "No current outages" zero state regardless
of why it is empty. One endpoint, one loader, no visibility logic.

*Alternative considered:* hiding the widget when the `epb` source is disabled (via the
`enabled` flag on `/timeseries/sources`). Rejected per review — the widget should not depend
on map/source settings, and the zero state covers the quiet case; the extra fetch and hidden
state bought complexity, not clarity.

### Permanent `timeseries` subscription, filtered client-side to `epb`
`live.ts` subscribes to the `timeseries` topic permanently (like the news/events/weather
subscriptions) and refetches the digest only when `msg.source === "epb"`. Diff messages carry
`source` at the top level, so the filter is one comparison; the diff payload itself is ignored
in favor of a refetch, matching the digest pattern (payload-applying is the map's concern).
This is the first permanent subscriber to the `timeseries` topic — the frontend-live spec
wording changes accordingly, and the bus already dispatches one topic to any number of
handlers, so no bus changes.

*Alternative considered:* applying the diff payload to home state (counts += new - closed).
Rejected — duplicate bookkeeping of ingest semantics for no user-visible gain at this scale.

### Home-owned component and state, styled via home.css
`OutageDigest.svelte` lives in the home feature with its own `home.outages*` state and
loaded/error flags, rendered between `WeatherStrip` and the events article inside
`widget-column`. Styling goes in `frontend/src/styles/home.css` per the global styling
contract (no scoped styles). No cross-feature imports are needed at all — the widget talks to
the timeseries *API*, not the timeseries feature's frontend namespace, keeping the home
feature's import-isolation rule trivially satisfied.

## Risks / Trade-offs

- **A burst of epb diffs (storm) causes refetch churn** → each diff triggers one small GET; the
  EPB poll interval paces broadcasts (one diff per cycle at most), so worst case is one refetch
  per poll interval — same cadence the map already sustains.
- **`customer_quantity` semantics differ between services** (fiber counts may be estimates) →
  the widget presents the number verbatim per service and never sums across services, so a
  skewed fiber estimate cannot distort the power figure.
- **With the `epb` source disabled the widget shows "No current outages" rather than
  disappearing** → accepted by design: the widget is unconditional, and a disabled collector
  is an admin-side state the home digest deliberately does not model.
- **Widget count in the right column grows** → the column stacks; on narrow viewports the
  documented stack order becomes news, weather, outages, events. Vertical budget is ~2 lines
  plus a heading in the common (quiet) case.

## Migration Plan

Frontend-only, additive. Deploy is the normal rebuild; rollback is reverting the change. No
config, schema, or API changes.

## Open Questions

- None blocking. Label wording ("power" vs "electric") and singular/plural forms can be settled
  in review; the spec's examples use "power".
