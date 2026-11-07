## Context

`WeatherService._fetch_aqi` calls `GET https://www.airnowapi.org/aq/observation/latLong/current/`
with `latitude`, `longitude`, `distance=25`, and `API_KEY`. `parse_airnow` then shapes the
response into `{value, category, category_name, pollutant, observed_at}`.

AirNow retired that endpoint on 2026-10-01. A live probe on 2026-11-06 using the
deployment's key showed the following:

| Request | Result |
|---|---|
| old `latLong/current` | `410`, `{"WebServiceError":[{"Message":"This web service has been retired as of October 1, 2026. ..."}]}` |
| new `current/ziplatlong`, Chattanooga center | `200`, one entry per pollutant (see below) |
| new endpoint, `distance=1` vs `distance=25` | identical output; `lookupBoundary` is always `"50 Miles"` |
| new endpoint, mid-Atlantic point | `200`, `{"WebServiceError":[{"Message":"There are no observations available ... within 50 miles."}]}` |
| new endpoint, bad key | `401`, `{"WebServiceError":[{"Message":"Invalid API key"}]}` |

New entry shape (Chattanooga, recorded):

```json
{"dateObserved":"2026-11-06","hourObserved":"22:00","localTimeZone":"EST",
 "reportingAreaName":"Chattanooga","siteID":"470654002","siteName":"Siskin Dr",
 "parameterName":"PM2.5","nowcastAQI":36,"aqiCategoryName":"Good",
 "reportingAgency":"Chattanooga-Hamilton County Air Pollution Control Bureau",
 "lookupBehavior":"Closest Reading By Pollutant","consideredMonitors":"All",
 "lookupBoundary":"50 Miles"}
```

A multi-pollutant location (Los Angeles) returns `PM2.5`, `OZONE`, and `PM10` entries.

Old payloads had a `Category: {Number, Name}` object. The new one has only `aqiCategoryName`.
The frontend's chip colors key off the numeric `category`.

## Goals / Non-Goals

**Goals:**
- Get AQI flowing again from the supported endpoint, with the existing key.
- Keep the `/api/v1/weather` `aqi` contract and the frontend exactly as they are.
- Make the next upstream break obvious in the logs, by logging AirNow's own message.

**Non-Goals:**
- Surfacing AirNow health on the debug page or in an API field. The existing
  graceful-degradation contract stays; only the log gets better.
- Using AirNow forecasts or the reporting-area endpoint.
- Normalizing pollutant names (`OZONE` → `O3`). The name passes through verbatim, as the
  spec already says for category names.

## Decisions

### D1. Use `/aq/observation/current/ziplatlong/` with lat/lon and no `distance`

The June 2026 AirNow notice names this endpoint as the replacement for both retired
current-observation services. Lat/lon keeps using the shared `center_lat`/`center_lon`
settings, as today. The `distance` parameter is dropped along with `AIRNOW_DISTANCE_MILES`,
because the service ignores it (the probe showed a fixed 50-mile lookup). Sending a no-op
parameter would suggest a radius control that does not exist.

*Alternatives:*
- `zipCode`: would add a setting that duplicates the center coordinate.
- `/aq/observation/current/racode/` (reporting area): needs a reporting-area code, which
  means a new setting.

### D2. Read the new fields; keep the worst-pollutant rule

`parse_airnow` picks the entry with the maximum numeric, non-negative `nowcastAQI`. It
reads `parameterName` as the pollutant and `aqiCategoryName` as the category name. The
-999 sentinel guard stays because it costs nothing. "Overall AQI = worst pollutant" is
still the EPA convention, and the new service still returns one entry per pollutant.

There is no fallback to the old PascalCase fields. The old endpoint is gone, so a dual
parser would be dead code.

### D3. Derive the category number from the AQI value

The EPA breakpoints are fixed:

| AQI value | Category |
|---|---|
| 0–50 | 1 |
| 51–100 | 2 |
| 101–150 | 3 |
| 151–200 | 4 |
| 201–300 | 5 |
| ≥ 301 | 6 |

A small pure helper applies them as upper bounds (`≤50`, `≤100`, …), so non-integer values
fall into the right category. This keeps the frontend's color keying unchanged.

*Alternatives:*
- Map `aqiCategoryName` strings to numbers: breaks if AirNow changes the wording, for
  example "Unhealthy for Sensitive Groups" vs. "USG".
- Drop `category` from the API and key colors on the name: a contract change with no benefit.

### D4. Parse `hourObserved` as `"HH:MM"`

`_observed_at` reads `dateObserved` (`YYYY-MM-DD`) and takes the hour from `hourObserved`.
That field is a string like `"22:00"`; a bare integer is also accepted, which costs one
`isinstance` check. Minutes are zeroed as before, since the data is hourly.

The `LocalTimeZone` → offset table and the naive-timestamp fallback stay unchanged. The
new service still returns standard-time abbreviations (`EST`, `PST`) in November, which
the table covers.

### D5. The error envelope means no usable AQI, and its messages get logged

AirNow returns `{"WebServiceError":[{"Message": ...}, ...]}` in two cases: with HTTP 200
when no monitor has data, and as the body of 4xx/410 errors.

- `parse_airnow` returns `None` for any non-list payload. It stays pure, and the existing
  carry-forward/staleness logic handles the rest.
- A pure helper `airnow_error_messages(payload) -> list[str]` pulls out the message strings.
  It returns `[]` for anything that is not the envelope.
- `_fetch_aqi` changes as follows:
  - On a non-2xx status, it decodes the body if it can. It logs one warning that includes
    the status code and AirNow's messages, for example
    `AirNow AQI fetch failed: HTTP 410: This web service has been retired as of October 1, 2026...`.
    It no longer logs a bare `raise_for_status` traceback.
  - On a 200 envelope, it logs one warning with the messages and returns `None`.
  - Network and decode errors keep the current `exc_info` warning.

The messages come from the response body, not the URL, so they cannot contain `API_KEY`.
The existing log-redaction filter still covers httpx's request line. The existing key-leak
test for 410/500 is kept and adapted. Its assertions about the `HTTPStatusError` traceback
are replaced by assertions about the status-plus-message line, and the "key not in log"
assertion stays.

## Risks / Trade-offs

- [AirNow changes the new payload again] → The parser reads the fields named in the spec.
  Any break degrades to `aqi: null` (after carry-forward), and the warning now carries
  AirNow's message.
- [The fixed 50-mile lookup may pick a farther monitor than the old 25-mile radius] → For
  Chattanooga the closest monitor is in-county (Siskin Dr). We accept this; the service
  offers no radius control.
- [Derived category could disagree with `aqiCategoryName` near a boundary] → Both come
  from the same `nowcastAQI` under the same EPA table, so they agree unless AirNow
  publishes a non-standard category. The name is still shown verbatim.
- [Logging the body on error statuses] → The body is AirNow's short JSON error. Only the
  `Message` strings are logged, not the raw body.

## Migration Plan

Code-only. Deploy with `docker compose up --build`. The next scheduled weather refresh
(≤ 10 minutes) populates `aqi`. No config change is needed. Rollback means reverting the
commit; the old endpoint would simply keep returning 410.
