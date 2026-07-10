# EPB Outage API

Reverse-engineered reference for the **EPB** (Electric Power Board of Chattanooga, TN)
outage map at <https://epb.com/outage-storm-center/>. Captured 2026-06-14. This is the
public data behind the "Automated Grid" map; documented here as a LocalDash source.

## How the map gets its data

The page's outage map is component **`c7100`** (`assets/component/js/modules/c7100/c7100.js`).
It does not fetch data directly — it calls a small client gateway:

```
c7100.js
  -> comepb/repository/outages.js        (getEnergyOutageIncidentsV2, getFiberOutageIncidentsV2, …)
    -> backends/gateway.js               (maps each method to a path under a base URL)
      -> base path from window.epb.backends.gateway
```

The base URL is injected into the page as a global:

```js
window.epb.backends = { gateway: "https://api.epb.com:443" }
```

and `gateway.js` builds the outage endpoints as `{base}/web/api/v2/outages/{service}` with
`/incidents` and `/restores` handlers (`gateway/outages.js`). So the effective base is:

```
https://api.epb.com/web/api/v2/outages
```

## Authentication

**None.** The incident/restore endpoints are unauthenticated `GET`s (only outage *reporting* —
`/power/report`, `/fiber/report` — needs an `X-User-Token`). Send `Accept: application/json`.

```bash
curl -s -H 'Accept: application/json' \
  https://api.epb.com/web/api/v2/outages/energy/incidents
```

## Request model — important

- Each call is a **point-in-time snapshot of currently-active outages** — no history, no
  `since`/pagination, no server-side filtering. Like hc911/tdot, LocalDash builds the
  time-series itself via the snapshot→diff ingest pipeline.
- **No per-incident id.** An incident is just `{customer_quantity, incident_status, latitude,
  longitude}`. The outage's *location* is its identity (it sits at a fixed feeder/transformer
  point while its status progresses), so LocalDash keys the entity on the rounded lat/lon,
  scoped by service: `external_id = "{service}:{lat:.6f},{lon:.6f}"`.
- The collector exposes `incident_status` under the canonical `properties["status"]` key, which
  is what the ingest state-change dedup and the frontend both read.

## Endpoints (base `https://api.epb.com/web/api/v2/outages`)

| Endpoint | Returns | Shape |
|---|---|---|
| `energy/incidents` | active power outages | `{ "incidents": [ … ] }` |
| `energy/restores`  | power locations restored in the last 24h | `{ "restores": [ … ] }` |
| `fiber/incidents`  | active fiber outages | `{ "incidents": [ … ] }` |
| `fiber/restores`   | fiber locations restored in the last 24h | `{ "restores": [ … ] }` |

> **`/restores` is intentionally not ingested.** Restores are recently-cleared locations with
> no status and no stable id — LocalDash already records restoration via the ingest **closure
> sweep** when an incident drops out of the `/incidents` snapshot, so polling `/restores` would
> only add duplicate, idless points. (There is also a legacy v1 `outages/power/incidents`.)

## Data shapes

### Incident object (`energy/incidents`, `fiber/incidents`)

```jsonc
{
  "customer_quantity": 123,                 // customers affected by this incident
  "incident_status": "OUTAGE_REPORTED",     // OUTAGE_REPORTED | EN_ROUTE | REPAIR_IN_PROGRESS
  "latitude": 35.022620,                    // fixed 6-decimal point (GeoJSON would be [lon, lat])
  "longitude": -85.444421
}
```

Observed `incident_status` values map to the map legend: `OUTAGE_REPORTED` ("Outage Reported"),
`EN_ROUTE` ("Crew En Route"), `REPAIR_IN_PROGRESS` ("Repair in Progress"). A point leaving the
feed corresponds to the legend's "Service Restored".

### Restore object (`*/restores`) — not ingested, for reference

```jsonc
{ "customer_quantity": 423, "latitude": 35.0698972701844, "longitude": -85.2435239357269 }
```

Note restores use full float precision (not the 6-decimal incident points) and carry no status.

## Mapping to LocalDash (`collectors/epb.py`)

- **`source_key`** = `epb`; one collector polls all configured services and merges them.
- **`category`** = the service (`energy` | `fiber`) — drives the marker color and filter.
- **`external_id`** = `"{service}:{lat:.6f},{lon:.6f}"` (no source id; location is identity).
- **`geom`** = `latitude`/`longitude` (remember GeoJSON is `[lon, lat]`).
- **`status`** = `incident_status`, also copied into `properties["status"]`.
- **`source_time`** = `None` — the feed has no timestamp; `observed_at` (poll time) is the clock.
- state-change detection handles status moves (`OUTAGE_REPORTED`→`EN_ROUTE`→…), and the closure
  sweep flips an outage inactive (= restored) when it drops out of the snapshot.

Configured via `epb_*` settings in `app/config.py` (`epb_api_base_url`, `epb_services`,
`epb_poll_interval`, `epb_enabled`).

### Quick probe commands

```bash
BASE=https://api.epb.com/web/api/v2/outages
curl -s -H 'Accept: application/json' "$BASE/energy/incidents" | jq '.incidents | length'
curl -s -H 'Accept: application/json' "$BASE/fiber/incidents"  | jq '.incidents[0]'
```
