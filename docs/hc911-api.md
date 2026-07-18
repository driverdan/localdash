# Hamilton County TN 911 — Active Incidents API

Reference for the upstream data feed behind
<https://www.hamiltontn911.gov/active-incidents.php>. This is an **unofficial**,
reverse-engineered description; the endpoint is undocumented and may change
without notice.

## Provenance

The public page `active-incidents.php` renders incidents on a Leaflet map. Its
`js/map.js` calls a JSON endpoint every 60 seconds and plots the results. The
endpoint, headers, and field handling below were derived from that script and
confirmed against live responses.

## Endpoint

```
GET https://hc911server.com/api/calls
```

Note the host (`hc911server.com`) differs from the page host
(`www.hamiltontn911.gov`).

### Required headers

| Header | Value | Notes |
| --- | --- | --- |
| `X-Frontend-Auth` | `my-secure-token` | A fixed, shared client token shipped in `map.js`. Required — requests without it are rejected. |
| `Origin` | `https://www.hamiltontn911.gov` | The server gates on Origin. |
| `Content-Type` | `application/json` | Sent by the site (not strictly needed for a GET, but harmless). |

A descriptive `User-Agent` is recommended as a courtesy (LocalDash sends one).

### Example

```bash
curl -s 'https://hc911server.com/api/calls' \
  -H 'X-Frontend-Auth: my-secure-token' \
  -H 'Origin: https://www.hamiltontn911.gov'
```

## Response

`200 OK` with a **JSON array** of active-call objects. There is no envelope,
pagination, or metadata — just the array.

```json
[
  {
    "id": 2336386,
    "master_incident_id": 9461112,
    "sequencenumber": "2026-06-19673",
    "status": "Enroute",
    "creation": "2026-06-13T18:49:26.000Z",
    "statusdatetime": "1900-01-01T00:00:00.000Z",
    "entered_queue": "2026-06-13T18:49:26.000Z",
    "type": "EMS CALL",
    "type_description": "EMS CALL",
    "priority": "PRI 1",
    "agency_type": "Law",
    "jurisdiction": "Chattanooga PD",
    "battalion": "CPD Adam 5",
    "zone": "A5",
    "location": "365 HAMM RD",
    "crossstreets": "DOGWOOD LN/MANUFACTURERS RD",
    "premise": "",
    "city": "CHATTANOOGA",
    "state": "TN",
    "latitude": 35.058036,
    "longitude": -85.324538,
    "stacked": false
  }
]
```

Typical response size is a few dozen records (~30–60).

### Key semantics

- **It is a snapshot, not a history.** The array contains only *currently active*
  calls. A call that closes simply disappears from subsequent responses; there is
  no "closed" record and no historical query. To build a time-series you must poll
  and track changes yourself (this is exactly what LocalDash does — see
  [How LocalDash consumes it](#how-localdash-consumes-it)).
- **Polling cadence: 60 seconds.** The site polls at this rate; do not poll faster.
- **`statusdatetime` uses a `1900-01-01T00:00:00.000Z` sentinel** to mean "no
  value" for many records. Treat any year < ~1990 as null. `creation` is reliable.
- All timestamps are **UTC ISO-8601** (`...Z`).

## Field reference

| Field | Type | Example | Notes |
| --- | --- | --- | --- |
| `id` | int | `2336386` | Per-row id. Unique within a response. |
| `master_incident_id` | int | `9461112` | **Stable incident id**; persists across polls as status changes. Use this as the entity key. |
| `sequencenumber` | string | `"2026-06-19673"` | Human-facing incident number. |
| `status` | string | `"Enroute"` | See enum below. |
| `creation` | string (ISO-8601 UTC) | `"2026-06-13T18:49:26.000Z"` | When the call was created. Reliable. |
| `statusdatetime` | string (ISO-8601 UTC) | `"1900-01-01T00:00:00.000Z"` | Time of current status; **often the 1900 sentinel** (= no value). |
| `entered_queue` | string (ISO-8601 UTC) | `"2026-06-13T18:49:26.000Z"` | When the call entered the dispatch queue. |
| `type` | string | `"EMS CALL"` | Call type (display). ~18+ distinct values; open-ended. |
| `type_description` | string | `"EMS CALL"` | Longer description; often equal to `type`. |
| `priority` | string | `"PRI 1"` | `PRI 1`–`PRI 4`, or `""` (empty) when unset. |
| `agency_type` | string | `"Law"` | `Law` / `Fire` / `EMS` / `HC911`. See enum. |
| `jurisdiction` | string | `"Chattanooga PD"` | Responding agency/jurisdiction. |
| `battalion` | string | `"CPD Adam 5"` | Unit/battalion assignment. |
| `zone` | string | `"A5"` | Dispatch zone. |
| `location` | string | `"365 HAMM RD"` | Address or block range (e.g. `"2200 - 2399 BROAD ST"`). |
| `crossstreets` | string | `"DOGWOOD LN/MANUFACTURERS RD"` | Nearby cross streets. |
| `premise` | string | `"@2 CARTER PLAZA"` | Premise/place name; often empty. |
| `city` | string | `"CHATTANOOGA"` | Upper-cased. |
| `state` | string | `"TN"` | Always `TN` in observed data. |
| `latitude` | float | `35.058036` | WGS84. May be missing/invalid for some calls. |
| `longitude` | float | `-85.324538` | WGS84. |
| `stacked` | bool | `false` | Whether the call is "stacked" (queued behind another). |

### Enumerated values (observed)

These are observed from live data, not a published spec — treat as open-ended.

- **`status`**: `Queued`, `Stacked`, `Enroute`, `On Scene`, `At Hospital`,
  `Transporting`.
- **`agency_type`**: `Law`, `Fire`, `EMS`, `HC911`.
- **`priority`**: `PRI 1`, `PRI 2`, `PRI 3`, `PRI 4`, `""`.
- **`type`**: open-ended free-text-ish list. Examples seen: `EMS CALL`,
  `MVC Injuries`, `MVC No Injuries`, `MVC Unknown Injuries`, `Disorder`,
  `Harassment`, `Civil Matter`, `Animal Call`, `Auto Broken Down`,
  `Check For A Hazard`, `Police Assist Citizen`, `Pursuit On Foot`,
  `Fire Special Assign`, `Miscellaneous Complaint`, `Property`.
- A special type **`PERBURN`** (permitted burns) appears in the raw feed but is
  **filtered out by the source site** before display.

## Behavioral notes & caveats

- **Filtering:** the website excludes records where `type == "PERBURN"`. LocalDash
  mirrors this.
- **Identity:** in observed snapshots both `id` and `master_incident_id` are unique
  per row (no single incident split across multiple agency rows in the samples
  taken). `master_incident_id` is the value that stays constant across polls and is
  therefore the stable key for tracking a call over time.
- **Missing coordinates:** some calls have absent or non-numeric `latitude` /
  `longitude`; consumers must handle null geometry.
- **Stability:** undocumented endpoint, fixed shared token, and Origin gating mean
  this can break at any time. Validate fields defensively.

## How LocalDash consumes it

The collector lives in [`app/collectors/hc911.py`](../app/collectors/hc911.py):

- `fetch()` issues the GET with the headers above (token/origin from settings).
- `normalize()` maps each record to a `NormalizedObservation`:
  - `external_id` = `master_incident_id` (stable entity key),
  - `category` = `Law→police`, `Fire→fire`, `EMS→ems`, everything else (incl.
    `HC911`) → `other`,
  - `lat`/`lon` parsed defensively (nulls allowed),
  - the full original record is preserved in `properties`,
  - `PERBURN` records are dropped,
  - `source_time` is taken from `statusdatetime` (falling back to `creation`),
    with the 1900 sentinel rejected.

The ingestion service then builds the time-series: it tracks each incident by
`master_incident_id`, appends a new observation only when status or position
changes, and marks a call closed (with a synthetic `Closed` observation) once it
disappears from the feed. Empirically, incidents accumulate multiple observations
across their lifetime (status `Queued → Enroute → On Scene → …`), confirming
`master_incident_id` is stable across polls. See
[`app/ingest.py`](../app/ingest.py) and the architecture notes in
[`CLAUDE.md`](../CLAUDE.md).

<!-- ci-skip verification: docs-only change, safe to revert -->
