# Tasks: add-chattlibrary-sources

## 1. News registry

- [x] 1.1 Add the `chattlibrary` source to `SOURCES` in `app/news/registry.py`: name
  "Chattanooga Public Library", homepage `https://chattlibrary.org`, one feed
  `https://chattlibrary.org/category/news/feed/` with category `life`; comment the single-feed
  choice (site-wide `/feed/` is identical today but unscoped; `/news/feed/` is an empty page
  feed) per the other outlets' annotation style, and update the requirement-level outlet count
  references if any test pins it
- [ ] 1.2 Add per-source feed-tag suppression (design.md D6): registry entries accept
  `use_feed_tags: False` (set on `chattlibrary` only — its posts all carry boilerplate
  `News`/`Featured` tags that would misfile every announcement under `news`), a registry helper
  exposes the flag by slug, and the fetcher passes an empty tag list to `classify()` for exempt
  sources so tiers 2/3 categorize instead

## 2. Tribe events source

- [x] 2.1 Add config to `app/config.py`: `events_tribe_calendars` (comma-separated `Name=BaseURL`,
  default `Chattanooga Public Library=https://chattlibrary.org`) and
  `events_tribe_lookahead_days: int = 14`
- [x] 2.2 Create `app/events/sources/tribe.py` with `TribeEventsSource(base_url, name,
  lookahead_days, timeout)`: async paginated fetch of
  `<base_url>/wp-json/tribe/events/v1/events` (`start_date`/`end_date` window, `per_page=50`,
  follow `total_pages` with a defensive page cap of 10, default UA), and a pure
  `parse(payload)` implementing the design.md D4 field mapping (unescaped title, HTML-stripped
  description via bs4, `utc_start_date`/`utc_end_date` as aware UTC with skip-and-warn on
  missing start, venue name/joined address, supplied `geo_lat`/`geo_lng`, `clean_image_url` on
  `image.url`, lowercased category names as tags, occurrence `id` as source event id)
- [x] 2.3 Wire configured calendars into `build_sources()` in `app/events/sources/__init__.py`:
  parse `events_tribe_calendars` entries on the first `=`, skip malformed entries with a logged
  warning, one `TribeEventsSource` per entry; update the module docstring's source inventory

## 3. Tests

- [x] 3.1 Capture a trimmed real API page as `tests/fixtures/` JSON (2–3 events covering: venue
  with geo + categories, venue without geo, missing `utc_start_date`, HTML
  description/entity title, two occurrences of one recurring series)
- [x] 3.2 Add `tests/test_events_tribe.py` offline parse tests for every spec scenario that is a
  pure-parse concern (field mapping, skip-and-warn, HTML reduction, distinct occurrences), plus
  pagination against a mocked two-page transport (pattern: `test_events_cityspark.py`)
- [x] 3.3 Add `build_sources()` config tests (in `tests/test_events_tribe.py`, mirroring how
  the CitySpark module owns its own `build_sources` tests): default registers the library calendar, override
  replaces it, empty disables, malformed entry skipped with warning (extend the existing
  sources-registry tests)
- [ ] 3.4 Add tag-suppression tests: an exempt source's mapped `News` tag is ignored (article
  falls through to the feed registration), a non-exempt source's tags still map, and the
  registry helper defaults to using tags when the key is absent

## 4. Verify and document

- [x] 4.1 Update docs that enumerate sources/settings (README/docs env-var tables if they list
  `events_ical_feeds`-style settings; AGENTS.md feature blurbs only if they enumerate outlets)
- [x] 4.2 Run the test suite, then rebuild and run via `sg docker -c 'docker compose up --build'`
  and verify: library articles appear under News with category `life`, library events appear
  with images/tags/venues, no geocoder traffic for geo-supplied venues (log check), and a
  second refresh creates no duplicate events (occurrence-id dedup)
  — verified 2026-07-17: 10 articles fetched (`chattlibrary/life: ok`); 104 events, all with
  geometry and images, many cross-source-merged with CitySpark's copies of the same programs;
  zero Nominatim calls; second refresh created 0. Caveat: every library post carries a WP
  `<category>News</category>` tag, so tier-1 classification stores all articles as `news` and
  the registered `life` fallback never fires (see PR discussion)
