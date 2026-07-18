## ADDED Requirements

### Requirement: Humanized status labels
The timeseries feature SHALL display a feature's `status` to the user through a source-aware
humanizing lookup rather than the raw upstream value. The per-source display config MAY declare a
`statusLabels` table mapping a raw status code to a human-readable label; a status with no table
entry (and any source with no table) SHALL fall back to the existing `catLabel()` humanizer. This
lookup SHALL be the single place status labels are produced and SHALL be applied at every surface
that shows a status to the user: the map marker popup, the map timeline-point tooltip, the incident
table's status cell, the detail panel's observation history, the EPB detail row, and the status
filter dropdown's option text.

The `epb` source SHALL populate `statusLabels` with `OUTAGE_REPORTED`→"Outage Reported",
`EN_ROUTE`→"Crew En Route", `REPAIR_IN_PROGRESS`→"Repair in Progress", and both `RESTORED` and
`Closed`→"Service Restored". Sources without machine-code statuses (`hc911`, `tdot`, `tnaw`) SHALL
declare no `statusLabels` and keep their `catLabel()`-humanized display unchanged.

The humanized label is a display concern only: `properties.status` SHALL continue to carry the raw
code, the status filter's stored value and `passesFilters` match SHALL remain the raw code, and the
status filter dropdown's `<option>` value SHALL remain the raw code while only its visible text is
humanized — so selecting a humanized label still filters on the underlying raw status.

#### Scenario: EPB status is humanized wherever it is shown
- **WHEN** an `epb` outage with status `REPAIR_IN_PROGRESS` appears in a popup, the incident table,
  the detail panel history, or the status filter dropdown
- **THEN** each surface displays "Repair in Progress" rather than the raw `REPAIR_IN_PROGRESS`

#### Scenario: Restored EPB outage collapses two codes to one label
- **WHEN** an `epb` outage carries status `RESTORED` or the closure sentinel `Closed`
- **THEN** it is displayed as "Service Restored"

#### Scenario: Source without a status table falls back to catLabel
- **WHEN** an `hc911` or `tdot` feature with a status is displayed and its source declares no
  `statusLabels`
- **THEN** its status is shown via the existing `catLabel()` humanizer, unchanged from before

#### Scenario: Filtering still matches the raw code behind a humanized option
- **WHEN** the user selects the "Repair in Progress" option in the status filter dropdown
- **THEN** the stored filter value is the raw `REPAIR_IN_PROGRESS` and only features whose
  `properties.status` equals `REPAIR_IN_PROGRESS` remain visible
