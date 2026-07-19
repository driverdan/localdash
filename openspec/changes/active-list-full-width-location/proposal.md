## Why

The Active list (incident table) lives in a fixed 340px sidebar and crams five columns
(source, category, status, type, location) into ~316px. The `location` field varies wildly
by source — empty for EPB, up to 140 characters for water advisories — so as a fixed column
it is simultaneously wasted space for some sources and badly truncated for others.

## What Changes

- Move each row's `location` content out of its own column into a full-width sub-line
  rendered beneath that row's other cells, so long location text can wrap and use the whole
  sidebar width instead of being squeezed into a narrow column.
- Drop the "Location" header; the table header becomes four columns (source, category, status,
  type).
- Omit the location sub-line entirely when a source has no location text (e.g. EPB), so those
  rows stay single-line with no empty gap.
- Keep each incident a single clickable unit: clicking anywhere on the row — cells or
  location sub-line — still opens the detail panel and focuses the map exactly as today.

## Capabilities

### New Capabilities
<!-- None: this refines an existing capability. -->

### Modified Capabilities
- `frontend-timeseries`: the "Incident table" requirement changes how the location field is
  presented — a full-width sub-line beneath each row rather than a fifth column, omitted when
  location is empty.

## Impact

- `frontend/src/features/timeseries/components/IncidentTable.svelte` — table markup restructured
  so each incident spans two rows (grouped) with a conditional full-width location sub-line.
- `frontend/src/styles/timeseries.css` — styling for the grouped row and location sub-line
  (border grouping, hover/click affordance across both lines).
- No changes to data, APIs, state, or the map. Row-click behavior (`openDetail` → detail panel +
  `flyToRequest`) is unchanged.
