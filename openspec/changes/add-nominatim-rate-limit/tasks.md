## 1. Configuration

- [ ] 1.1 Add `events_geocoder_min_interval_seconds: float = 1.0` to `Settings` in
  `app/config.py`, with a comment noting Nominatim's 1 req/s policy
- [ ] 1.2 Pass the setting into `NominatimGeocoder` where it is constructed in
  `app/events/refresh.py`

## 2. Throttle implementation

- [ ] 2.1 Add `min_interval` parameter (default `1.0`) to `NominatimGeocoder.__init__`,
  storing an `asyncio.Lock` and a monotonic next-allowed-send timestamp
- [ ] 2.2 In `geocode()`, reserve the next send slot under the lock
  (`slot = max(now, next_slot)`; `next_slot = slot + min_interval`), release the lock,
  and `asyncio.sleep` until the slot before sending the HTTP request
- [ ] 2.3 Skip the reservation/sleep entirely when `min_interval <= 0`
- [ ] 2.4 Update the module docstring in `app/events/geocoding.py` (it currently says
  "no additional throttling yet")

## 3. Tests

- [ ] 3.1 Unit test: with a small `min_interval` (e.g. 0.05s) and a mocked transport,
  sequential `geocode()` calls record send times spaced ≥ `min_interval` apart
- [ ] 3.2 Unit test: concurrent `geocode()` calls (`asyncio.gather`) are also spaced
  ≥ `min_interval` apart — no stampede through the lock
- [ ] 3.3 Unit test: `min_interval=0` adds no delay between calls
- [ ] 3.4 Unit test: empty address still returns `None` without consuming a throttle slot

## 4. Verification

- [ ] 4.1 Run the full test suite
- [ ] 4.2 Rebuild and run via `sg docker -c 'docker compose up --build'`, trigger
  `POST /api/v1/events/refresh` with a fresh address, and confirm ingest still geocodes
  and logs no errors
