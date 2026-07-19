## Context

The Active list is `IncidentTable.svelte`, a `<table>` in the 340px `#sidebar` with columns
source / category / status / type / location. Rows are clickable (`openDetail` opens the detail
panel and sets `ts.flyToRequest`). Base table styling lives in `base.css`; feature-specific rules
(clickable rows, hover, closed-row muting) live in `timeseries.css`.

The `location` accessor (`cfgFor(source).location`) is per-source and highly variable: `hc911`
returns an address, `tdot` a description or county, `epb` always `""`, `tnaw` up to 140 chars. As a
fixed fifth column in a narrow sidebar this is both wasted space and heavy truncation.

## Goals / Non-Goals

**Goals:**
- Render each entity's location as a full-width line beneath its other cells, wrapping freely.
- Drop the location column from the header (four columns remain).
- Omit the location line when location text is empty, keeping such rows single-line.
- Preserve the existing single-click-to-focus behavior across the whole entity unit.

**Non-Goals:**
- No change to which entities are shown, sort order, filtering, or the live count.
- No change to the map, detail panel, state, or data accessors.
- Not moving `type` (`cfg.title`) down; only `location` relocates.

## Decisions

**One `<tbody>` per entity (grouped rows), not colspan pairing or a div-based card list.**
A single `<table>` may contain multiple `<tbody>` elements. Each entity becomes its own `<tbody>`
holding a header `<tr>` (four `<td>`: source, category, status, type) and, when location is
non-empty, a second `<tr>` whose single `<td colspan="4">` carries the full-width location.
- Why over **colspan alone (two `<tr>` in one tbody)**: with a shared tbody, `:hover` and the
  clickable unit would span the pair only via fragile sibling logic; grouping the pair in its own
  tbody lets `tbody:hover` and per-tbody handlers target the whole entity cleanly.
- Why over **div-based cards**: keeps the existing header-aligned columns and base table styling;
  smaller diff; no re-implementation of column layout.

**Conditional location line.** Compute `const loc = cfg.location(p)` once per entity; render the
second `<tr>` only inside `{#if loc}`. Empty-location sources (EPB) render a single header row.

**Click handling on both inner rows.** Move `onclick={() => openDetail(f)}` onto both the header
`<tr>` and the location `<tr>` (or onto the `<tbody>` if the click handler placement allows), so a
click anywhere on the entity focuses it. Keep the existing a11y-ignore comments.

**Border/visual grouping in CSS.** Base `td` sets a bottom border per cell. Regroup so the visual
divider falls between *entities* (bottom of each `tbody`), not between an entity's header and its
location line: suppress the header row's bottom border when a location line follows, and hover both
inner rows together via `#incident-table tbody:hover`. `closed-row` muting continues to apply to
both inner rows.

## Risks / Trade-offs

- **Header no longer labels the location line** → Acceptable: location is self-evident and already
  unlabeled context; the sub-line reads as a continuation of the row above it.
- **Multiple `<tbody>` is less common markup** → Valid HTML and well supported; documented with a
  comment in the component so the structure isn't mistaken for an error.
- **Hover/click now spans two rows** → Mitigated by scoping hover/click to the `tbody` so the whole
  entity highlights and responds as one unit.
- **Closed-row italic/muted styling must reach the location line** → Ensure the `closed-row` class
  (or its selector) covers both inner rows, not just the header row.
