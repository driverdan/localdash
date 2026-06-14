# TDOT SmartWay API

Reverse-engineered reference for the Tennessee DOT **SmartWay** traffic map
(<https://smartway.tn.gov/traffic>). Captured 2026-06-13. This is the public-facing
data that backs the Leaflet map; documented here as a candidate second LocalDash source.

## How the map gets its data

SmartWay is an Angular SPA. On boot it fetches a runtime config from the **same origin** it
is served from:

```
GET https://smartway.tn.gov/config/config.prod.json
```

That config (reproduced below) contains the **real API base URL and a hard-coded API key**,
plus the endpoint path for each map layer. The SPA then calls
`{apiBaseUrl}{layerEndpoint}` for each enabled layer.

```json
{
  "apiBaseUrl": "https://www.tdot.tn.gov/opendata/api/public/",
  "apiKey": "8d3b7a82635d476795c09b2c41facc60",
  "incidents": "RoadwayIncidents",
  "construction": "RoadwayOperations",
  "cameras": "RoadwayCameras",
  "messageSigns": "RoadwayMessageSigns",
  "restAreas": "RestAreas",
  "specialEvents": "RoadwaySpecialEvents",
  "weather": "RoadwayWeather",
  "countywideWeather": "RoadwayCountyWideWeather",
  "severeImpact": "RoadwaySevereImpact",
  "waze": "https://spatial.tdot.tn.gov/ArcGIS/rest/services/WAZE/Waze_Smartway/MapServer/0/query?...&f=json",
  "projects": "https://experience.arcgis.com/experience/e3a1da3b4ea24ce190b0395702f5b9f6/",
  "countyPolygon": "https://services2.arcgis.com/nf3p7v7Zy4fTOh6M/arcgis/rest/services/Administrative_Boundaries_Prod_Data/FeatureServer/7/"
}
```

> The `apiKey` is shipped to every browser in cleartext (it is a static app key, not a
> per-user secret). Re-read `config.prod.json` before relying on the value above — TDOT can
> rotate it at any time, and the config is the source of truth.

## Authentication

Pass the key either way (both verified working):

- **Header (what the SPA uses):** `X-API-Key: <apiKey>`
- **Query param:** `?apiKey=<apiKey>`

No key → **HTTP 401**. `Ocp-Apim-Subscription-Key` is rejected (it's a plain key, not APIM).

```bash
curl -s -H "X-API-Key: 8d3b7a82635d476795c09b2c41facc60" \
  https://www.tdot.tn.gov/opendata/api/public/RoadwayIncidents
```

## Request model — important

- **No server-side filtering.** Passing `region`, `countyId`, `countyName`, or `bbox` does
  **not** change the response — every endpoint returns the **full statewide snapshot** and the
  SPA filters by viewport client-side. (Filter on `locations[].countyName`/`region` or by
  point geometry yourself.)
- Each call is a **point-in-time snapshot of currently-active items** — there is no history
  and no `since`/pagination. This mirrors the hc911 source: LocalDash would construct the
  time-series itself via the existing snapshot→diff ingest pipeline.
- Responses are top-level **JSON arrays** (not GeoJSON). `RoadwayWeather` /
  `RoadwayCountyWideWeather` currently return **HTTP 204 (no content)** — present but empty.

## Endpoints (base `https://www.tdot.tn.gov/opendata/api/public/`)

| Endpoint | Layer | Geometry | Notes |
|---|---|---|---|
| `RoadwayIncidents` | Incidents (crashes, congestion, disabled/overturned vehicles) | point + routeLine | Event object (see below) |
| `RoadwayOperations` | Construction / maintenance / road work | point + routeLine | Same Event object; large (~250 items) |
| `RoadwaySpecialEvents` | Special events affecting roadways | point + routeLine | Same Event object |
| `RoadwaySevereImpact` | Severe-impact events (closures, major delays) | point + routeLine | Same Event object; `isSevere=true` |
| `RoadwayCameras` | ~670 traffic cameras / CCTV | lat/lng point | HLS/RTMP/RTSP stream URLs + thumbnail |
| `RoadwayMessageSigns` | ~230 dynamic message signs (DMS) | lat/lng point | Current `message` text |
| `RestAreas` | ~35 rest areas / welcome centers | lat/lng point | Open/closed status |
| `RoadwayWeather` | Roadway weather (RWIS) | — | **204 empty** when nothing active |
| `RoadwayCountyWideWeather` | County-wide weather alerts | — | **204 empty** when nothing active |

External (ArcGIS REST, **no API key**, standard Esri query params incl. real bbox/geometry):

- **Waze traffic** — `https://spatial.tdot.tn.gov/ArcGIS/rest/services/WAZE/Waze_Smartway/MapServer/0/query`
  This is the `features=traffic` layer: crowdsourced Waze alerts (~60 live points). Supports
  full ArcGIS querying (`where=1=1`, `geometry`/`geometryType=esriGeometryEnvelope` for bbox,
  `returnGeometry`, `outFields=*`, `f=json|geojson`, `returnCountOnly=true`).
- **County polygons** — `services2.arcgis.com/.../Administrative_Boundaries_Prod_Data/FeatureServer/7/`
- **Projects** — an ArcGIS Experience Builder app (HTML, not a data API).

## Data shapes

### Event object — Incidents / Operations / SpecialEvents / SevereImpact (shared schema)

```jsonc
{
  "id": 2236598,
  "status": "Unresolved",              // enum: "Unresolved" | "Confirmed"
  "eventTypeId": 3,
  "eventTypeName": "Incident",         // "Incident" | "Operations" | "SpecialEvent"
  "eventSubTypeId": 0,
  "eventSubTypeDescription": "Congestion",
  "description": "Interstate 24 EB in Hamilton County - near MILE MARKER 182 ...",
  "currentActivity": null,             // free-text narrative (often set on Operations)
  "beginningDate": "2026-06-13T09:42:21.07-05:00",   // ISO8601 w/ offset (Central time)
  "endingDate": null,
  "revisedDate": "2026-06-13T09:42:42.34-05:00",     // last update
  "hasClosure": false,
  "isSevere": false,
  "wideArea": false, "memberOfWideArea": false,
  "primaryEventId": null, "parentId": null,
  "mileMarker": 182.0,
  "directionDescription": "Eastbound", // Eastbound|Westbound|Northbound|Southbound|Both Directions
  "impactDescription": "Eastbound no lanes blocked",
  "oppositeImpactDescription": "",
  "diversionDescription": "", "dayOfWeek": "",
  "thpReported": false,                // TN Highway Patrol reported
  "locations": [{
    "type": "Point",
    "midPoint": { "lat": 35.019349, "lng": -85.266656 },
    "coordinates": [{ "lat": 35.019349, "lng": -85.266656 }],
    "routeLine": [[ { "lat": ..., "lng": ... }, ... ]],   // polyline(s) along the road
    "oppositeImpactRouteLine": [],
    "region": 2,                       // TDOT region 1-4
    "countyId": 33, "countyName": "Hamilton"
  }]
}
```

Observed `eventSubTypeDescription` values (non-exhaustive): `Congestion`, `Disabled Vehicle`,
`Overturned Vehicle`, `Special Event`, and construction subtypes (`Bridge Repair`,
`Bridge Replacement`, `Bridge Work`, `Milling`, `Emergency Road Work`, `Interchange
Modification`, `Intersection Modification`, `Other Construction`, `Other Maintenance`).

**Note the coordinate convention:** points are `{lat, lng}` objects (and `routeLine` is an
array of arrays of them), **not** GeoJSON `[lng, lat]`. Convert before storing.

### RoadwayCameras

```jsonc
{
  "id": 3165,
  "title": "I-40/75 @ West Hills",
  "description": "I-40/75 @ West Hills",
  "thumbnailUrl": "https://tnsnapshots.com/thumbs/R1_010.flv.png",
  "httpVideoUrl":  "https://....skyvdn.com:443/rtplive/R1_010/playlist.m3u8",  // HLS
  "httpsVideoUrl": "https://....skyvdn.com:443/rtplive/R1_010/playlist.m3u8",
  "rtmpVideoUrl":  "rtmp://....:1935/rtplive/R1_010",
  "rtspVideoUrl":  "rtsp://....:554/rtplive/R1_010",
  "clspUrl": null, "clspsUrl": "clsps://....:443/R1_010",
  "active": "true",                    // string, not bool
  "jurisdiction": "Knoxville", "route": "I-40", "mileMarker": "380.8",
  "lat": 35.928889, "lng": -84.039167,
  "location": { "type": "point", "coordinates": [{ "lat": ..., "lng": ... }] }
}
```

### RoadwayMessageSigns (DMS)

```jsonc
{
  "id": "1108",
  "title": "(30)I-40EB W/O Rockwood Mntn",
  "message": "",                        // current sign text ("" = blank/off)
  "region": 1, "route": "Interstate 40",
  "location": { "type": "point", "coordinates": [{ "lat": 35.884983, "lng": -84.809391 }] },
  "graphic": null
}
```

### RestAreas

```jsonc
{
  "id": 27,
  "displayName": "Rest Area on I-24 EB at MM 160",
  "isOpen": true,
  "county": null, "region": 2, "route": "Interstate 24",
  "type": "Rest Stop", "mile": 160,
  "lat": 35.024057, "lng": -85.558988,
  "begLogMile": 0, "sectionId": null,
  "events": [], "plannedClosure": null
}
```

### Waze traffic (ArcGIS layer fields)

Point layer `Waze Smartway`. Fields: `UUID`, `PUBLISH_DATETIME` (date), `TYPE`, `SUBTYPE`,
`REPORT_DESC`, `STREET`, `CITY`, `COUNTRY`, `MAGVAR`, `REPORT_RATING`, `RELIABILITY`,
`ROAD_TYPE`, `OBJECTID`. Request `f=geojson` to get GeoJSON directly.

## Mapping to LocalDash (`collectors/`)

A `BaseCollector` subclass fits cleanly — these are snapshots, exactly like hc911:

- **`source_key`** per layer (e.g. `tdot_incidents`, `tdot_cameras`, …) or one collector
  emitting multiple sources.
- **`external_id`** = `id` for each item (stable per event/camera/sign).
- **`geom`** = `locations[0].midPoint` (or `lat`/`lng` for cameras/signs/rest areas), remembering
  to flip to GeoJSON `[lng, lat]`. Stash `routeLine` in `properties` for line rendering.
- **`source_time`** = `revisedDate` (events) / `PUBLISH_DATETIME` (waze). As with hc911, keep
  `observed_at` = poll time; events carry real timestamps (no 1900 sentinel seen).
- **state-change detection** already handles status moves (`Unresolved`→`Confirmed`→absent)
  and the closure sweep (item drops out of the snapshot → mark inactive).
- Put everything source-specific (`eventSubTypeDescription`, `impactDescription`, stream URLs,
  `message`, etc.) in `properties` JSONB — no schema change needed.

### Quick probe commands

```bash
KEY=8d3b7a82635d476795c09b2c41facc60
BASE=https://www.tdot.tn.gov/opendata/api/public
curl -s -H "X-API-Key: $KEY" "$BASE/RoadwayIncidents" | jq length
curl -s -H "X-API-Key: $KEY" "$BASE/RoadwayCameras"   | jq '.[0]'
# Waze (no key), Chattanooga-ish bbox, as GeoJSON:
curl -s "https://spatial.tdot.tn.gov/ArcGIS/rest/services/WAZE/Waze_Smartway/MapServer/0/query?where=1%3D1&outFields=*&returnGeometry=true&f=geojson"
```
