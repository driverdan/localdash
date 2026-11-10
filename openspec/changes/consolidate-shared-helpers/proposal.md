## Why

Small helpers have been copied from module to module as sources were added:

- the same NaN-rejecting float coercion in three collectors
- five near-identical "ISO string to aware UTC" parsers under three names
- two identical `_as_utc` functions
- two EWKT point builders
- six hand-rolled comma-split loops over settings
- the same keyword-table matching loop in the news classifier and the events tagger
- in the news fetcher, the same raw-content extraction twice and the same article row dict twice

Each copy is a place where a fix has to be made more than once.

Some copies look alike but behave differently. The CarCruiseFinder parser treats naive timestamps
as America/New_York, and the four HTML-to-text helpers produce different text. Those differences
are easy to lose, and events de-duplication depends on them, because `canonical_key` hashes the
parsed title and start hour.

This change depends on `relax-backend-feature-separation`, which lands first. That change records
that backend packages under `app/` are for organisation, not boundaries: any backend module may
import from any other, and shared code is preferred over copies. This change applies that
guideline to these specific helpers and adds no import rules of its own.

## What Changes

- New shared modules at the top of `app/`, for helpers whose callers span more than one package:
  - `app/timeutil.py`: `as_utc(value, naive_tz=UTC)` and `parse_iso_utc(value, naive_tz=UTC)`.
  - `app/geo.py`: `ewkt_point(lat, lon)`.
  - `app/text.py`: `keyword_matches(text, table)`, plus `strip_html` and `truncate_sentences`
    moved from `app/news/textutil.py`, which keeps the clustering-specific `title_tokens` and
    `STOPWORDS`.
- **Merged** (the copies behave identically):
  - `_as_float` (hc911, tdot, epb) becomes `as_float` in `app/collectors/base.py`.
  - `_as_utc` (events `ingest.py` and `dedup.py`) becomes `app.timeutil.as_utc`. The datetime
    branch of the iCal `_to_aware_utc` also delegates to it.
  - The EWKT point strings in `app/ingest.py` and `app/events/ingest.py` become `ewkt_point`.
  - The tribe and CitySpark `_join_address` bodies become one `join_address(parts)` in
    `app/events/sources/base.py`. Each source keeps choosing its own fields.
  - The keyword-matching loop in `app/news/classify.py` (tier 2) and `app/events/tagging.py`
    becomes `keyword_matches`. It yields matching table keys in table order:
    - classify takes the first match;
    - tagging takes the set of all matches.

    The keyword tables stay separate data in their own modules.
  - In `app/news/fetcher.py`: one `_entry_raw_content(entry)` feeds both `_entry_summary` and
    `_entry_image`, and one `_article_row(...)` builder serves the RSS and HTML paths.
- **Merged with a parameter** (the copies differ only in a real parameter):
  - The tdot `_parse_dt`, tribe and CitySpark `_parse_utc` and Meetup `_to_aware_utc` read naive
    values as UTC. The CarCruiseFinder `_to_aware_utc` reads them as `America/New_York`. All become
    `parse_iso_utc(value, naive_tz=...)`.
  - hc911 `_parse_dt` keeps its name and its 1990 sentinel check, as a two-line wrapper over
    `parse_iso_utc`.
  - Comma-separated settings are split by one `split_csv()` in `app/config.py`. The plain lists
    become `Settings` properties, following the existing `blocked_tags` property. The tnaw
    `layer:category` entries and the tribe `Name=BaseURL` entries keep their entry parsing where it
    is, and malformed tribe entries are still skipped with a warning.
- **Left alone** (they differ in kind; reasons in design.md):
  - the four HTML-to-text helpers. Their output differs, and it feeds stored text and
    `canonical_key`.
  - the Meetup and CarCruiseFinder address builders. Their output differs, and it feeds
    geocode-cache keys.
  - the iCal date/datetime coercion.
  - the tribe `_coord` helper.
- `_fetch_html_feed` drops its unused `source_slug` parameter.

**Observable changes.** For every well-formed upstream value, these outputs stay byte-identical:
parsed timestamps, addresses, text, geometry, news categories and event topic tags. So
`canonical_key`, geocode-cache keys and change-detection fingerprints are unaffected. There are two
edge-case changes, both on malformed or unusual input:

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

- `app-shell`: adds a requirement that the backend has exactly one implementation each of
  datetime-to-UTC normalisation, ISO-timestamp parsing (with the naive-value zone as a parameter),
  EWKT point building, comma-separated settings splitting and keyword-table matching. It also
  states that consolidating them leaves parsed timestamps, news categories and event tags
  unchanged. It sets no import rules and does not say where code must live.

## Impact

- New: `app/timeutil.py`, `app/geo.py`, `app/text.py`, `tests/test_timeutil.py`,
  `tests/test_geo.py`, `tests/test_text.py`.
- Edited:
  - `app/config.py`, `app/ingest.py`
  - `app/collectors/{base,hc911,tdot,epb,tnaw}.py`
  - `app/events/{ingest,dedup,tagging}.py`
  - `app/events/sources/{__init__,base,tribe,cityspark,meetup,carcruisefinder,ical}.py`
  - `app/news/{classify,fetcher,stories,textutil}.py`
  - `AGENTS.md` (factual mentions only)
- Tests:
  - `tests/test_hc911_helpers.py`, `tests/test_events_ingest.py` and
    `tests/test_news_clustering.py` change their imports.
  - `tests/test_config.py` and `tests/test_news_fetcher.py` gain cases.
  - All existing source, classify and tagging tests must pass unchanged. They are the
    behaviour-preservation gate.
- No API, schema, migration, dependency or frontend changes.
