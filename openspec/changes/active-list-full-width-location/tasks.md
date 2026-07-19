## 1. Restructure the table markup

- [x] 1.1 In `IncidentTable.svelte`, drop the `Location` `<th>` so the header row is four columns
  (Source, Category, Status, Type).
- [x] 1.2 Change the `{#each}` body so each entity renders as its own `<tbody>` containing a header
  `<tr>` with the four cells (source, category, status, type) — removing the location `<td>` from it.
- [x] 1.3 Compute `const loc = cfg.location(p)` per entity and render a second `<tr>` with a single
  `<td colspan="4">{loc}</td>` only inside `{#if loc}`, so empty-location entities (EPB) stay
  single-row.
- [x] 1.4 Attach the `openDetail(f)` click handler and the `closed-row` class so they cover the whole
  entity (both the header row and the location sub-line), keeping the existing a11y-ignore comments.
- [x] 1.5 Add a brief comment explaining the one-`<tbody>`-per-entity grouping.

## 2. Style the grouped rows

- [x] 2.1 In `timeseries.css`, update the clickable/hover rules to target `#incident-table tbody`
  (per-entity) so hover and the pointer cursor cover both inner rows as one unit.
- [x] 2.2 Regroup borders so the divider falls between entities: suppress the header row's bottom
  border when a location sub-line follows, keeping a single rule under each `tbody`.
- [x] 2.3 Style the full-width location sub-line (indent/padding, muted/secondary text) so it reads as
  a continuation of the row above and wraps cleanly.
- [x] 2.4 Ensure `closed-row` muting (faint italic) applies to both the header row and the location
  sub-line.

## 3. Verify

- [x] 3.1 Rebuild via Docker (`docker compose up --build`) and load the map dashboard.
- [x] 3.2 Confirm a `tnaw` advisory shows its long location wrapping full-width, an `epb` outage
  shows no location sub-line, and clicking anywhere on an entity (header or location line) opens the
  detail panel and focuses the map.
- [x] 3.3 Confirm closed entities render muted across both lines and the header shows four columns.
