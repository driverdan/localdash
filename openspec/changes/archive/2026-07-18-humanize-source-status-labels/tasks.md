## 1. Lookup layer in sources.ts

- [x] 1.1 Add optional `statusLabels?: Record<string, string>` to `SourceConfig` in `frontend/src/features/timeseries/types.ts`
- [x] 1.2 Populate `statusLabels` on the `epb` config in `sources.ts`: `OUTAGE_REPORTED`→"Outage", `EN_ROUTE`→"En Route", `REPAIR_IN_PROGRESS`→"Repairing", `RESTORED`→"Restored", `Closed`→"Closed"
- [x] 1.3 Export `statusLabel(source, raw)` in `sources.ts`: return `cfgFor(source).statusLabels?.[raw] ?? catLabel(str(raw))`
- [x] 1.4 Export source-agnostic `statusLabelForRaw(raw)` in `sources.ts`: scan all configured `statusLabels` tables for the raw code, else `catLabel(str(raw))` — for the pooled/per-feature display sites that lack a paired source
- [x] 1.5 Switch the EPB detail row (`sources.ts:134`) from `catLabel(str(p.status))` to `statusLabel("epb", p.status)`

## 2. Apply at every display site

- [x] 2.1 Map popup (`components/MapView.svelte:181`): humanize via `esc(statusLabelForRaw(p.status))`
- [x] 2.2 Map timeline-point tooltip (`components/MapView.svelte:261`): humanize `t.status` via `statusLabelForRaw`
- [x] 2.3 Incident table status cell (`components/IncidentTable.svelte:40`): humanize `p.status` via `statusLabelForRaw`
- [x] 2.4 Detail panel observation history (`components/DetailPanel.svelte:56`): humanize `t.status` via `statusLabelForRaw`
- [x] 2.5 Filter dropdown (`components/FilterPanel.svelte:76`): render `<option value={v}>{statusLabelForRaw(v)}</option>` — value stays the raw code, only text is humanized

## 3. Verify

- [x] 3.1 Confirm the status filter still narrows correctly: selecting "Repairing" filters to features whose raw `status` is `REPAIR_IN_PROGRESS`, and the stale-selection reset still works
- [x] 3.2 Confirm `hc911`/`tdot`/`tnaw` statuses render unchanged (via `catLabel` fallback)
- [x] 3.3 Run frontend checks (`svelte-check` / lint) and rebuild Docker per AGENTS.md, verify an EPB outage shows humanized status in popup, table, detail panel, and dropdown
