# Tasks: add-chattlibrary-sources

## 1. News registry

- [ ] 1.1 Add the `chattlibrary` source to `SOURCES` in `app/news/registry.py`: name
  "Chattanooga Public Library", homepage `https://chattlibrary.org`, one feed
  `https://chattlibrary.org/category/news/feed/` with category `life`; comment the single-feed
  choice (site-wide `/feed/` is identical today but unscoped; `/news/feed/` is an empty page
  feed) per the other outlets' annotation style, and update the requirement-level outlet count
  references if any test pins it

## 2. Tribe events source

- [ ] 2.1 Add config to `app/config.py`: `events_tribe_calendars` (comma-separated `Name=BaseURL`,
  default `Chattanooga Public Library=https://chattlibrary.org`) and
  `events_tribe_lookahead_days: int = 14`
- [ ] 2.2 Create `app/events/sources/tribe.py` with `TribeEventsSource(base_url, name,
  lookahead_days, timeout)`: async paginated fetch of
  `<base_url>/wp-json/tribe/events/v1/events` (`start_date`/`end_date` window, `per_page=50`,
  follow `total_pages` with a defensive page cap of 10, default UA), and a pure
  `parse(payload)` implementing the design.md D4 field mapping (unescaped title, HTML-stripped
  description via bs4, `utc_start_date`/`utc_end_date` as aware UTC with skip-and-warn on
  missing start, venue name/joined address, supplied `geo_lat`/`geo_lng`, `clean_image_url` on
  `image.url`, lowercased category names as tags, occurrence `id` as source event id)
- [ ] 2.3 Wire configured calendars into `build_sources()` in `app/events/sources/__init__.py`:
  parse `events_tribe_calendars` entries on the first `=`, skip malformed entries with a logged
  warning, one `TribeEventsSource` per entry; update the module docstring's source inventory

## 3. Tests

- [ ] 3.1 Capture a trimmed real API page as `tests/fixtures/` JSON (2–3 events covering: venue
  with geo + categories, venue without geo, missing `utc_start_date`, HTML
  description/entity title, two occurrences of one recurring series)
- [ ] 3.2 Add `tests/test_events_tribe.py` offline parse tests for every spec scenario that is a
  pure-parse concern (field mapping, skip-and-warn, HTML reduction, distinct occurrences), plus
  pagination against a mocked two-page transport (pattern: `test_events_cityspark.py`)
- [ ] 3.3 Add `build_sources()` config tests: default registers the library calendar, override
  replaces it, empty disables, malformed entry skipped with warning (extend the existing
  sources-registry tests)

## 4. Verify and document

- [ ] 4.1 Update docs that enumerate sources/settings (README/docs env-var tables if they list
  `events_ical_feeds`-style settings; AGENTS.md feature blurbs only if they enumerate outlets)
- [ ] 4.2 Run the test suite, then rebuild and run via `sg docker -c 'docker compose up --build'`
  and verify: library articles appear under News with category `life`, library events appear
  with images/tags/venues, no geocoder traffic for geo-supplied venues (log check), and a
  second refresh creates no duplicate events (occurrence-id dedup)
