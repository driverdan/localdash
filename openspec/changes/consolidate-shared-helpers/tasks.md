## 1. Pin current behaviour first

- [ ] 1.1 Before touching any helper, run `pytest tests/test_hc911_helpers.py tests/test_tdot.py tests/test_epb.py tests/test_tnaw.py tests/test_events_*.py tests/test_news_fetcher.py tests/test_news_html_scrape.py tests/test_config.py` and record that it is green. These existing tests are the preservation gate. Only the import edits named in 3.3 and 4.4 may change them.
- [ ] 1.2 Add characterisation cases where the current tests leave gaps, against today's code, and commit them first: tdot naive `revisedDate` read as UTC; a tribe event and a CitySpark event with an offset (non-`Z`) UTC field; and the iCal all-day `date` mapping to midnight UTC (if not already covered).

## 2. Shared time module

- [ ] 2.1 Create `app/timeutil.py` (stdlib imports only) with `as_utc(value, naive_tz=timezone.utc)` and `parse_iso_utc(value, naive_tz=timezone.utc)`, as specified in design D2. Add docstrings that state the naive-value rule.
- [ ] 2.2 Add `tests/test_timeutil.py` covering:
  - `as_utc`: an aware non-UTC value, a naive value with the default zone, and a naive value with `America/New_York`.
  - `parse_iso_utc`: a `Z` suffix, a `+00:00` offset, a `-05:00` offset, naive with the default zone, and naive with `America/New_York` in both winter (EST) and summer (EDT).
  - `parse_iso_utc` returning `None` for `""`, `None`, `12345` and `"not-a-date"`.
- [ ] 2.3 Replace `_as_utc` in `app/events/ingest.py` and `app/events/dedup.py` with `app.timeutil.as_utc`, and delete both local copies.
- [ ] 2.4 `app/events/sources/ical.py`: keep `_to_aware_utc`, but make its `datetime` branch return `as_utc(value)`.
- [ ] 2.5 Replace tdot `_parse_dt`, tribe `_parse_utc`, CitySpark `_parse_utc` and Meetup `_to_aware_utc` with `parse_iso_utc`, and delete the local copies.
- [ ] 2.6 CarCruiseFinder: replace `_to_aware_utc` with `parse_iso_utc(value, naive_tz=LOCAL_TZ)`, and keep `LOCAL_TZ` and its comment.
- [ ] 2.7 hc911: reduce `_parse_dt` to a wrapper that calls `parse_iso_utc` and returns `None` when the year is below 1990. Keep the sentinel comment, and add a short note that naive values are read as UTC.

## 3. Collector float coercion

- [ ] 3.1 Move `_as_float` to `as_float` in `app/collectors/base.py`, or the timeseries collectors' `base.py` if `move-timeseries-into-package` has landed.
- [ ] 3.2 Import it in `hc911.py`, `tdot.py` and `epb.py`, and delete the three local copies.
- [ ] 3.3 `tests/test_hc911_helpers.py`: import `as_float` from the base module. The assertions stay unchanged.

## 4. EWKT point

- [ ] 4.1 Create `app/geo.py` (stdlib only) with `ewkt_point(lat, lon) -> str` returning `f"SRID=4326;POINT({lon} {lat})"`.
- [ ] 4.2 `app/ingest.py` `_geom_value`: use `ewkt_point(obs.lat, obs.lon)`.
- [ ] 4.3 `app/events/ingest.py`: delete `_point`, and use `ewkt_point(*coords)` at every former call site.
- [ ] 4.4 `tests/test_events_ingest.py`: replace the two `_point` imports with `from app.geo import ewkt_point`, and call it with unpacked coordinates.
- [ ] 4.5 Add `tests/test_geo.py`: `ewkt_point(35.04, -85.31) == "SRID=4326;POINT(-85.31 35.04)"`.

## 5. Event address join

- [ ] 5.1 Add `join_address(parts: Iterable[object]) -> str | None` to `app/events/sources/base.py`, using the exact tribe/CitySpark expression.
- [ ] 5.2 Make tribe and CitySpark `_join_address` pass their own field tuples to `join_address`.
- [ ] 5.3 Leave Meetup `_format_address` and CarCruiseFinder `_join_address` unchanged (design D3).

## 6. Comma-separated settings

- [ ] 6.1 Add a module-level `split_csv(value: str) -> list[str]` to `app/config.py`. It splits on commas, strips each entry, drops empty entries and keeps order.
- [ ] 6.2 Rewrite `blocked_tags` with `split_csv`, keeping the same signature and result.
- [ ] 6.3 Add the properties `tdot_endpoint_list`, `epb_service_list` and `events_ical_feed_list`, and read them in `TdotCollector.__init__`, `EpbCollector.__init__` and `build_sources`.
- [ ] 6.4 Make tnaw `_parse_layers` and the tribe loop in `build_sources` use `split_csv` for the split only. Keep their entry parsing, and keep the malformed-tribe warning on the `localdash.events` logger.
- [ ] 6.5 In `tests/test_config.py`, test `split_csv`: blanks, whitespace, a trailing comma, and an empty string giving `[]`. Also test each new property against its default value and an overridden one.

## 7. News fetcher

- [ ] 7.1 Add `_entry_raw_content(entry) -> str`, and call it from `_entry_summary` and `_entry_image`.
- [ ] 7.2 Add `_article_row(feed, *, guid, url, title, summary, image_url, tags, published, now) -> dict`, and use it in both `fetch_feed` (RSS) and `_fetch_html_feed`. Keep the explanatory comments about the tags choice at each call site.
- [ ] 7.3 Remove the unused `source_slug` parameter from `_fetch_html_feed`, and update its call in `fetch_feed`.
- [ ] 7.4 In `tests/test_news_fetcher.py`, add `_entry_summary` cases for each priority: `content` beats `summary`, which beats `description`. Add an `_article_row` case that checks the 9 keys and that the HTML-style call passes `[]` tags.

## 8. Docs and verification

- [ ] 8.1 Update `AGENTS.md`:
  - Add a short "Shared backend helpers" note under Architecture. It names `app/timeutil.py` and `app/geo.py`, and gives the rule: stdlib only, never import a feature package, and only for helpers that more than one feature uses; anything else stays in the feature. Point to the `lib/` rule as the frontend counterpart.
  - In "Adding a data source", mention `as_float` in the collectors' base module and `parse_iso_utc(..., naive_tz=...)` for source timestamps.
- [ ] 8.2 Grep for leftovers. `rg "def _(as_float|as_utc|parse_utc|point)\b|def _to_aware_utc|def _parse_dt" app` should find only iCal `_to_aware_utc` and hc911 `_parse_dt`. `rg "\.split\(\",\"\)" app` should find only `split_csv`, the `bbox` query parser in `app/api/timeseries.py` and the address splitting in `app/events/geocoding.py`. The last two parse request and address data rather than settings, so they are out of scope.
- [ ] 8.3 Run the full `pytest` suite against the Dockerised DB, then `ruff check` and `ruff format --check`.
- [ ] 8.4 Rebuild and start the stack with `docker compose up --build`. Trigger `POST /api/v1/events/refresh` and `POST /api/v1/news/refresh`, and check that the events count does not jump (no new `canonical_key` duplicates) and that the news feed statuses are unchanged.
