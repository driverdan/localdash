## Why

`NominatimGeocoder` fires requests against the public OpenStreetMap Nominatim service as fast
as the ingest loop iterates. Nominatim's usage policy caps clients at an absolute maximum of
1 request/second; a burst of uncached addresses (e.g., onboarding a new event source such as
the pending carcruisefinder scraper) violates the policy and risks getting the deployment
blocked. The permanent `geocode_cache` keeps steady-state volume near zero, but nothing
protects the burst case today.

## What Changes

- Add client-side rate limiting to `NominatimGeocoder` so outbound requests are spaced at
  least 1 second apart (at most 1 request/second), including across concurrent callers.
- Make the minimum request interval configurable via settings, defaulting to 1 second, so a
  future self-hosted Nominatim (`base_url` override) can relax or disable the throttle.
- No behavior change for cache hits: throttling applies only when a request actually goes out.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `events`: The "Address geocoding with a permanent cache" requirement gains a rate-limit
  clause — Nominatim requests SHALL be spaced by a configurable minimum interval
  (default 1s), per the service's usage policy.

## Impact

- `app/events/geocoding.py`: throttle logic in `NominatimGeocoder`.
- `app/config.py`: new setting for the minimum request interval.
- `app/events/refresh.py`: pass the configured interval when constructing the geocoder.
- Tests: new unit tests for request spacing; existing ingest tests unaffected (they use
  fakes, not `NominatimGeocoder`).
- Runtime effect: initial ingest of a source with N uncached addresses takes ~N seconds of
  geocoding time; refresh is a background job, so this is acceptable.
