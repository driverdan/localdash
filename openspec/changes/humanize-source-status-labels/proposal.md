## Why

EPB outage statuses reach the UI as raw upstream codes (`OUTAGE_REPORTED`, `EN_ROUTE`,
`REPAIR_IN_PROGRESS`) and are shown verbatim in the map popup, timeline tooltip, incident table,
detail panel, and filter dropdown. Only the EPB detail row attempts to humanize them, via
`catLabel()`, which mechanically produces "OUTAGE REPORTED" and can never yield the labels EPB's own
map uses ("Crew En Route", "Service Restored"). The status label is the one piece of status metadata
that isn't centralized.

## What Changes

- Add a single centralized status-label lookup for `properties.status`: a per-source lookup table
  keyed by raw status code, falling back to the existing `catLabel()` humanizer when a code has no
  entry.
- Populate the EPB table only (the sole source with machine-code statuses today):
  `OUTAGE_REPORTED`→"Outage Reported", `EN_ROUTE`→"Crew En Route",
  `REPAIR_IN_PROGRESS`→"Repair in Progress", `RESTORED`/`Closed`→"Service Restored". Other sources
  (`hc911`, `tdot`, `tnaw`) have no entries and keep their `catLabel()`-humanized display, unchanged.
- Apply the lookup everywhere a feature's status is displayed to the user: the map popup, the map
  timeline-point tooltip, the incident-table status cell, the detail-panel observation history, the
  status filter dropdown's option **text**, and the EPB detail row.
- Keep the status filter dropdown's `<option>` **value** as the raw status code (only the visible
  text is humanized) so `passesFilters` still matches on the raw `p.status`.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `frontend-timeseries`: status is displayed to the user through a source-aware humanizing lookup
  (raw codes for filter identity, humanized labels for display) across the map, table, detail panel,
  and filter dropdown.

## Impact

- `frontend/src/features/timeseries/sources.ts` — add a per-source `statusLabels` table (EPB
  populated) and a `statusLabel(source, raw)` helper alongside the existing `catLabel`.
- `frontend/src/features/timeseries/types.ts` — optional `statusLabels` field on `SourceConfig`.
- Display sites: `components/MapView.svelte` (popup + timeline tooltip),
  `components/IncidentTable.svelte`, `components/DetailPanel.svelte`,
  `components/FilterPanel.svelte` (option text only).
- No backend, API, or data-shape changes; `properties.status` still carries the raw code, and the
  status filter still matches on it.
