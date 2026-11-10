## Why

Small helpers have been copied from module to module as sources were added: the same NaN-rejecting
float coercion in three collectors, five near-identical "ISO string to aware UTC" parsers under
three names, two identical `_as_utc` functions, two EWKT point builders, six hand-rolled
comma-split loops over settings, and in the news fetcher the same raw-content extraction twice and
the same article row dict twice. Each copy is a place where a fix has to be made more than once.
Some copies also look alike but behave differently. The CarCruiseFinder parser treats naive
timestamps as America/New_York, and the four HTML-to-text helpers produce different text. Those
differences are easy to lose, and events de-duplication depends on them, because `canonical_key`
hashes the parsed title and start hour.

## What Changes

- New feature-agnostic backend modules at the top of `app/`, which import no feature package:
  - `app/timeutil.py`: `as_utc(value, naive_tz=UTC)` and `parse_iso_utc(value, naive_tz=UTC)`.
  - `app/geo.py`: `ewkt_point(lat, lon)`.
- Merged, because the copies behave identically:
  - `_as_float` (hc911, tdot, epb) becomes `as_float` in `app/collectors/base.py`. All three
    users are collectors, so it stays inside the timeseries feature.
  - `_as_utc` (events `ingest.py` and `dedup.py`) becomes `app.timeutil.as_utc`. The datetime
    branch of the iCal `_to_aware_utc` also delegates to it.
  - The EWKT point strings in `app/ingest.py` and `app/events/ingest.py` become
    `app.geo.ewkt_point`.
  - The tribe and CitySpark `_join_address` bodies become one `join_address(parts)` in
    `app/events/sources/base.py`. Each source keeps choosing its own fields.
  - In `app/news/fetcher.py`: one `_entry_raw_content(entry)` feeds both `_entry_summary` and
    `_entry_image`, and one `_article_row(...)` builder serves the RSS and HTML paths.
- Merged with a parameter, because the copies differ only in a real parameter:
  - The tdot `_parse_dt`, tribe and CitySpark `_parse_utc`, Meetup `_to_aware_utc` (naive values
    read as UTC) and CarCruiseFinder `_to_aware_utc` (naive values read as `America/New_York`)
    become `parse_iso_utc(value, naive_tz=...)`.
  - hc911 `_parse_dt` keeps its name and its 1990 sentinel check as a two-line wrapper over
    `parse_iso_utc`.
  - Comma-separated settings are split by one `split_csv()` in `app/config.py`. The plain lists
    become `Settings` properties, following the existing `blocked_tags` property. The tnaw
    `layer:category` and tribe `Name=BaseURL` entries keep their entry parsing where it is, and
    malformed tribe entries are still skipped with a warning.
- Left alone, because they differ in kind (reasons in design.md): the four HTML-to-text helpers,
  the Meetup and CarCruiseFinder address builders, the iCal date/datetime coercion, and the tribe
  `_coord` helper.
- `_fetch_html_feed` drops its unused `source_slug` parameter.
- `AGENTS.md` documents the shared backend modules and their import rule.

**Observable changes.** Parsed timestamps, addresses, text and geometry for every well-formed
upstream value stay byte-identical, so `canonical_key`, geocode-cache keys and change-detection
fingerprints are unaffected. There are two edge-case changes, both on malformed or unusual input:

- A truthy non-string timestamp (for example a number) in a tribe, CitySpark, Meetup or
  CarCruiseFinder payload now parses as missing. Today it raises `TypeError`, which fails that
  source's whole fetch. tribe and CitySpark now skip just that event with their existing warning.
- An hc911 timestamp without an offset is now read as UTC. Today it is read in the host's local
  time zone. The feed always sends a `Z` suffix, and the Docker image runs in UTC, so this changes
  nothing in production.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `app-shell`: adds a requirement that shared backend helpers live in feature-agnostic modules
  that import no feature package. It is the backend counterpart of the `frontend/src/lib/` import
  rule in `frontend-shell`, and it requires one implementation each of ISO-timestamp parsing and
  comma-separated settings splitting.

## Impact

- New: `app/timeutil.py`, `app/geo.py`, `tests/test_timeutil.py`, `tests/test_geo.py`.
- Edited: `app/config.py`, `app/ingest.py`, `app/collectors/{base,hc911,tdot,epb,tnaw}.py`,
  `app/events/{ingest,dedup}.py`,
  `app/events/sources/{__init__,base,tribe,cityspark,meetup,carcruisefinder,ical}.py`,
  `app/news/fetcher.py`, `AGENTS.md`.
- Tests: `tests/test_hc911_helpers.py` and `tests/test_events_ingest.py` change their imports;
  `tests/test_config.py` and `tests/test_news_fetcher.py` gain cases. All existing source tests
  must pass unchanged, and they serve as the behaviour-preservation gate.
- No API, schema, migration, dependency or frontend changes.
