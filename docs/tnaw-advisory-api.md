# Tennessee American Water Advisory API

Reverse-engineered reference for the **Tennessee American Water** (Chattanooga-area water)
service advisories, sourced from the public American Water **Customer Advisory Map**
<https://awgis.amwater.com/CustomerAdvisoryMap/>. Captured 2026-07-14. Documented here as a
LocalDash source (`source_key = tnaw`). Tennessee American Water is the dominant
Chattanooga-area water provider and the only one with machine-readable outage/advisory data;
the smaller districts (Hixson, Eastside, Walden's Ridge) publish text-only alert pages.

## How the map gets its data

The advisory map is an Esri **Web AppBuilder** app (`jimu.js`). It loads a public webmap
whose single operational layer is an ArcGIS MapServer — the trail:

```
awgis.amwater.com/CustomerAdvisoryMap/            (Web AppBuilder app)
  -> config.json  ->  webMap itemId 3791d39fd2384eb7947769093b9dc53b   (org AMWater, public)
       -> https://www.arcgis.com/sharing/rest/content/items/3791d39fd2384eb7947769093b9dc53b/data?f=json
            -> operationalLayer "American Water Customer Advisory Map Details":
               https://utility.arcgis.com/usrsvcs/servers/482bbe2135c54d178ec406189303faf4
                 /rest/services/CustomerAdvisoryMap/DisplayData_SDE/MapServer
```

The MapServer has three **polygon** layers:

| Layer | Name | Ingested? |
|---|---|---|
| 17 | Active Advisory – Emergency | yes → `category = emergency` |
| 16 | Active Advisory – General   | yes → `category = general` |
| 15 | Lifted Advisory             | **no** (see below) |

> **Layer 15 (Lifted) is intentionally not ingested.** A lifted advisory is simply one that
> has left the two Active layers, so LocalDash records it going away via the ingest **closure
> sweep** when its `EventID` drops out of the Active snapshot. Polling the Lifted layer would
> only re-add already-closed advisories.

## Authentication

**None.** The service is reached through ArcGIS Online's public `usrsvcs` proxy and needs no
token (the webmap item is `access: public`). Send `Accept: application/json`.

> ⚠️ **Fragility caveat.** This is a premium-proxied endpoint
> (`utility.arcgis.com/usrsvcs/...`), not a first-party American Water API. It is public today
> but could change or start requiring a token. Fetch errors are captured into the source's
> `last_status` / `last_error` telemetry without crashing the scheduler; if the shape changes,
> re-derive the operational-layer URL from the webmap item id above.

## Request model — important

- The feed is **national**. Filter to Tennessee **server-side** with the query
  `where=EventState='TN'` (configurable via `tnaw_state`); forgetting it pulls hundreds of
  out-of-region advisories.
- Each query is a **point-in-time snapshot of currently-active advisories** — LocalDash builds
  the time-series itself via the snapshot→diff ingest pipeline (as with hc911/tdot/epb).
- Every advisory has a **stable `EventID`**, used directly as the entity `external_id` (no
  lat/lon derivation like epb).
- Geometry is a **`Polygon`** (occasionally `MultiPolygon`) affected area — the reason this
  source drove the geo stack's generalization from Point-only to arbitrary geometry.

## Endpoint

```
GET {base}/{layer}/query
      ?where=EventState='TN'
      &outFields=*
      &returnGeometry=true
      &outSR=4326
      &f=geojson
```

with `base` =
`https://utility.arcgis.com/usrsvcs/servers/482bbe2135c54d178ec406189303faf4/rest/services/CustomerAdvisoryMap/DisplayData_SDE/MapServer`
and `layer` ∈ {`17`, `16`}. Returns a GeoJSON `FeatureCollection` of polygon features.

## Data shape

```jsonc
{
  "type": "Feature",
  "geometry": { "type": "Polygon", "coordinates": [ [ [lon, lat], … ] ] },
  "properties": {
    "EventID": "130266",                 // stable id -> external_id
    "EventNotificationType": "General",  // General | Emergency (mirrors the layer)
    "EventType": "Planned Work",          // Planned Work | Emergency Repair | … -> status
    "EventState": "TN",
    "EventStatus": "Active",
    "EventHeader": "Chattanooga: Planned Water System Improvements : …",  // -> label / title
    "EventMessage": "…full advisory text…",
    "EventHyperlink": "https://alertsdetail.awapps.com/alert/130266",
    "EventStartDate": 1739188800000,      // epoch ms
    "EventCompletionDate": 1756677600000,
    "EventExpirationDate": 1788235200000,
    "EventLastUpdatedDate": 1738870603000
  }
}
```

## Mapping to LocalDash (`collectors/tnaw.py`)

- **`source_key`** = `tnaw`; one collector polls both Active layers and merges them, keyed by
  `EventID` (an advisory returned by more than one layer resolves to one entity).
- **`category`** = the layer's advisory type (`emergency` | `general`) — drives the polygon
  color and the filter tree.
- **`external_id`** = `str(EventID)`.
- **`geometry`** = the GeoJSON polygon, stored verbatim (the generalized `geometry` column).
- **`status`** = `EventType` (falls back to `EventStatus`), also copied to `properties["status"]`.
- **`label`** = `EventHeader`.
- **`source_time`** = `None`; `observed_at` (poll time) is the series clock.
- State-change detection records a new observation when `status` or the affected-area geometry
  changes; the closure sweep flips an advisory inactive when it leaves the Active layers
  (= lifted).

Configured via `tnaw_*` settings in `app/config.py` (`tnaw_api_base_url`, `tnaw_state`,
`tnaw_layers`, `tnaw_poll_interval`, `tnaw_enabled`).

### Quick probe commands

```bash
BASE="https://utility.arcgis.com/usrsvcs/servers/482bbe2135c54d178ec406189303faf4/rest/services/CustomerAdvisoryMap/DisplayData_SDE/MapServer"
# TN active-general advisories as GeoJSON
curl -s "$BASE/16/query?where=EventState='TN'&outFields=*&returnGeometry=true&outSR=4326&f=geojson" | jq '.features | length'
# All layers / metadata
curl -s "$BASE?f=json" | jq '.layers'
```
