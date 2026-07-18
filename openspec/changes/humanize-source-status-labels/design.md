## Context

`properties.status` is a generic, source-agnostic field. Three sources emit human-ish statuses
already (`hc911`, `tdot`, `tnaw`); only `epb` emits machine codes (`OUTAGE_REPORTED`, `EN_ROUTE`,
`REPAIR_IN_PROGRESS`, plus `RESTORED`/`Closed`). Those codes are rendered raw in six display sites
today, and the one site that tries to humanize them (`sources.ts:134`, EPB detail row) uses
`catLabel()`, which only does `_`→space + capitalize-first — it yields "OUTAGE REPORTED" and cannot
express "Crew En Route" or fold two codes into "Service Restored".

`sources.ts` is already the designated home for all source-specific display knowledge (per the
`frontend-timeseries` "Per-source display configuration" requirement), and `catLabel` already lives
there as the generic humanizer. This change slots a lookup layer in front of `catLabel` in the same
module.

## Goals / Non-Goals

**Goals:**
- One function produces every user-visible status label; no display site formats status inline.
- EPB codes render exactly as EPB's own map labels them.
- The status filter keeps working: display is humanized, identity/matching stays on the raw code.
- Adding labels for a future source is a one-line table entry, no new code paths.

**Non-Goals:**
- No i18n framework, locale files, `t()` runtime, or multi-language support — the app is
  single-locale (English, Chattanooga). This is a display-label lookup, not translation infrastructure.
- No backend/API/data-shape change; `properties.status` still carries the raw code.
- No change to marker colors (`EPB_STATUS_COLORS`) or to any non-status display.

## Decisions

**Per-source `statusLabels` table + a `statusLabel(source, raw)` helper, both in `sources.ts`.**
Add an optional `statusLabels?: Record<string, string>` to `SourceConfig` (`types.ts`) and populate
only the `epb` config. Export `statusLabel(source: string, raw: unknown): string` that looks up
`cfgFor(source).statusLabels?.[raw]` and falls back to `catLabel(raw)`. Chosen over a single global
dictionary because status is source-scoped in principle (two sources could reuse a code with
different meanings) and this mirrors the existing per-source config pattern exactly. The EPB detail
row's current `catLabel(str(p.status))` becomes `statusLabel("epb", p.status)`, and it now resolves
correctly instead of "OUTAGE REPORTED".

**The lookup keys off the raw code; the filter dropdown splits value from text.** `FilterPanel`
renders `<option value={v}>{statusLabel(?, v)}</option>` — value stays raw so `passesFilters`
(`p.status === this.status`) and `statusOptions` (built from raw `p.properties.status`) are
untouched. Only the option's visible text changes. This keeps filter identity and display cleanly
separated and avoids reworking any filter/matching logic.

**Dropdown source resolution.** `statusOptions` is a flat list of raw status strings pooled across
all loaded sources, with no source attached. Since EPB is the only source with a `statusLabels`
table and its codes don't collide with other sources' status strings, the dropdown can resolve a
label by scanning all configured `statusLabels` tables for the raw code and falling back to
`catLabel` — i.e. a source-agnostic `labelForStatus(raw)` variant for the pooled-options case. This
avoids threading a source through the options list. (If two sources ever defined the same raw code
with different labels, the pooled dropdown would need per-option source context; noted as a
non-issue today and called out under Risks.)

**Where each site calls it:**
| Site | File | Change |
|---|---|---|
| Map popup | `MapView.svelte:181` | `esc(statusLabelForRaw(p.status))` |
| Timeline tooltip | `MapView.svelte:261` | `statusLabelForRaw(t.status)` |
| Incident table cell | `IncidentTable.svelte:40` | `statusLabelForRaw(p.status)` |
| Detail history | `DetailPanel.svelte:56` | `statusLabelForRaw(t.status)` |
| Filter option text | `FilterPanel.svelte:76` | `<option value={v}>{statusLabelForRaw(v)}</option>` |
| EPB detail row | `sources.ts:134` | `statusLabel("epb", p.status)` |

The popup, tooltip, table, detail history, and dropdown all render pooled/per-feature status without
a guaranteed source-vs-status pairing at hand, so they use the source-agnostic
`statusLabelForRaw(raw)`; only the EPB detail row (inside the `epb` config) knows its source and uses
the source-keyed `statusLabel("epb", …)`.

## Risks / Trade-offs

- **Two sources reusing one raw code with different labels** → the source-agnostic
  `statusLabelForRaw` would pick whichever table it scans first. Not possible today (only EPB has a
  table, no code collisions). Mitigation if it arises: give the pooled surfaces per-feature source
  context and always use the source-keyed `statusLabel`.
- **A status code EPB adds later with no table entry** → falls back to `catLabel`, so it degrades to
  the readable-but-imperfect form (e.g. "PARTIALLY RESTORED"), never to a crash or blank. Acceptable;
  fixed by adding one table row.
- **Search over status** (`passesFilters` builds its haystack from raw `p.status`) stays on the raw
  code, so typing "restored" won't match `RESTORED`. Out of scope here — the requirement scopes the
  humanization to displayed status; search behavior is unchanged and not regressed.
