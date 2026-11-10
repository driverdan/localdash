## Context

A Python architecture review listed small helpers that were copied as sources were added. I read
every body on `origin/main` before deciding anything, because several copies look alike but
behave differently. The table below records what each copy actually does.

| Group | Sites | What the bodies actually do |
|---|---|---|
| float coercion | `collectors/hc911.py:97`, `tdot.py:126`, `epb.py:93` | Identical: `float(v)`, `None` on `TypeError`/`ValueError` or NaN. |
| ISO string → aware UTC | `collectors/tdot.py:42` `_parse_dt` | `None` if falsy or not `str`; `fromisoformat`; naive → UTC; `astimezone(UTC)`. |
| | `events/sources/tribe.py:41`, `cityspark.py:57` `_parse_utc` | Same as tdot but **no `str` guard**: a truthy non-string raises `TypeError`. |
| | `events/sources/meetup.py:55` `_to_aware_utc` | Same as tribe (branches written the other way round, same results). |
| | `events/sources/carcruisefinder.py:56` `_to_aware_utc` | Same as tribe, except **naive → `America/New_York`** (`LOCAL_TZ`). |
| | `collectors/hc911.py:24` `_parse_dt` | `str` guard; `replace("Z", "+00:00")` (redundant: `fromisoformat` accepts `Z` since 3.11); `year < 1990` → `None` (the 1900 sentinel); then **`astimezone(UTC)` on a possibly naive value, which reads a naive time in the host's local zone**. |
| | `events/sources/ical.py:51` `_to_aware_utc` | Takes `date`/`datetime` **objects**, not strings; a `date` becomes midnight UTC. Its `datetime` branch matches `_as_utc`. |
| datetime → UTC | `events/ingest.py:103`, `events/dedup.py:69` `_as_utc` | Identical: naive → UTC, else `astimezone(UTC)`. |
| EWKT point | `app/ingest.py:90`, `events/ingest.py:38` `_point` | Identical output `SRID=4326;POINT({lon} {lat})`. Callers pass `(lat, lon)` in different shapes. |
| address join | `tribe.py:67`, `cityspark.py:136` `_join_address` | Identical join: `", ".join(p.strip() for p in parts if isinstance(p, str) and p.strip()) or None`. Field lists differ. |
| | `carcruisefinder.py:76` `_join_address` | Accepts a string or a schema.org dict; **runs each part through `_clean_text`** (entity decode + markup strip). |
| | `meetup.py:86` `_format_address` | **No strip, no `str` filter; falls back to the venue name.** |
| HTML → text | `news/textutil.py:31` `strip_html` | `html.unescape` first, stdlib `HTMLParser`, data parts joined with `" "`, all whitespace collapsed. |
| | `tribe.py:54` `_strip_html` | BeautifulSoup `get_text(" ", strip=True)`: no pre-unescape (encoded markup stays literal), no collapsing of whitespace inside a text node. |
| | `carcruisefinder.py:68` `_clean_text` | Pre-unescape, BeautifulSoup `get_text()` **with no separator** (adjacent elements run together), whitespace collapsed. Feeds event **titles**. |
| | `chattzoo.py:89` `_clean_text` | Takes a BeautifulSoup **node**, not a string. |
| CSV settings | `config.py:149` `blocked_tags`; `tdot.py:78`; `epb.py:44`; `tnaw.py:33` `_parse_layers`; `events/sources/__init__.py:54,57` | Same split/strip/drop-empty loop each time. tnaw adds `layer:category` parsing (category defaults to `general`). tribe adds `Name=BaseURL` parsing and skips malformed entries with a warning on `localdash.events`. |
| news fetcher | `news/fetcher.py:53-59` and `75-79` | Identical raw-content extraction (`content[0].value`, else `summary`, else `description`). |
| | `fetcher.py:201-216` and `243-262` | The same 9-key row dict. They differ only in where values come from and in the tags passed to `classify` (`[]` for HTML). |
| | `fetcher.py:189` `_fetch_html_feed` | The `source_slug` parameter is never read. |
| keyword matching | `news/classify.py:165-168` (tier 2) | Haystack `f" {title} {summary} ".lower()`; returns the **first** category in table order with any keyword as a substring. |
| | `events/tagging.py:33` `tag_text` | Haystack `f" {text.lower()} "` with `text = f"{title} {description}"`; returns the **set** of all topics with any keyword as a substring. |
| text utilities | `news/textutil.py` | `strip_html` and `truncate_sentences` are general-purpose, used by `fetcher.py` and `stories.py`. `title_tokens` and `STOPWORDS` exist only for `clustering.py`. |

The events gotchas in `AGENTS.md` set the constraint for this change. `canonical_key` hashes the
normalised title and the UTC start hour. Any change to how a source parses a timestamp, or how it
cleans a title, moves events to new keys and breaks cross-source de-duplication against rows
already stored. Address strings are geocode-cache keys, so changing them would cause extra
Nominatim lookups.

## Goals / Non-Goals

**Goals:**

- One implementation each of: float coercion, datetime → UTC, ISO string → UTC, EWKT point, the
  shared address join, comma-separated setting splitting, keyword-table matching, feed raw-content
  extraction, and the article row.
- Byte-identical output for every well-formed upstream value. Where a malformed-input edge case
  changes, state it.
- Put each helper where it reads best for its callers. This change applies the guideline from
  `relax-backend-feature-separation` (backend packages are organisation, not boundaries) and adds
  no rule of its own.

**Non-Goals:**

- Merging the HTML-to-text helpers or the address builders whose output differs.
- Merging the news and events keyword *tables*. They are separate vocabularies; only the matching
  mechanism is shared (D8).
- Writing the backend separation guideline into `AGENTS.md` or the specs. That belongs to
  `relax-backend-feature-separation`.
- The browser User-Agent constants and httpx clients (`add-shared-http-client`).
- The `MatchSide` and backfill duplication in `app/events/ingest.py` (`decompose-events-upsert`).
- Typing the article row (`add-typed-contracts`).

## Decisions

### D1. Placement, decided on the merits of each helper

`relax-backend-feature-separation` lets any backend module import any other, so where each helper
goes depends only on what reads best:

- **`app/timeutil.py`** (`as_utc`, `parse_iso_utc`). Callers are collectors, event sources, events
  ingest and events dedup, so no single package owns it. A small top-level module named for what
  it does sits naturally next to `config.py` and `redaction.py`. I rejected
  `app/collectors/base.py`: someone reading an event source should not have to look in the
  collector framework for a generic time helper.
- **`app/geo.py`** (`ewkt_point`). Callers are `app/ingest.py` and `app/events/ingest.py`. I
  rejected `app/geojson.py`: that module shapes GeoJSON API responses and holds timeseries
  `entity_properties`, while EWKT is a database write format. A separate module keeps each module
  about one thing.
- **`app/text.py`** (`keyword_matches`, `strip_html`, `truncate_sentences`) holds general text
  handling. The keyword matcher has callers in news and events (D8, D9).
- **`as_float` stays in `app/collectors/base.py`.** All three callers are collectors, every
  collector already imports this module, and the function sits beside `NormalizedObservation`,
  whose `lat` and `lon` it feeds. A top-level module would add a file without adding a caller. The
  tribe `_coord` helper is not a fourth copy: it rejects booleans and strings.
- **`join_address` goes in `app/events/sources/base.py`**, beside `clean_image_url`, the other
  small normalisation helper that event sources share. Its only callers are event sources.
- **`split_csv` goes in `app/config.py`**, because its only callers parse `Settings` fields (D5).

I rejected an `app/common/` or `app/utils/` package. Three small modules named for what they do
are easier to find than a generic bucket, and a generic bucket attracts unrelated code.

### D2. Time parsing: merge `as_utc`, parametrise `parse_iso_utc` on `naive_tz`

```python
def as_utc(value: datetime, naive_tz: tzinfo = timezone.utc) -> datetime: ...
def parse_iso_utc(value: object, naive_tz: tzinfo = timezone.utc) -> datetime | None:
    # None if falsy or not str; None on ValueError; else as_utc(fromisoformat(value), naive_tz)
```

| Copy | Choice | Call |
|---|---|---|
| events `_as_utc` ×2 | **merge** | `as_utc(t)` |
| iCal `_to_aware_utc` | **leave** (it takes date and datetime objects, so it differs in kind); its datetime branch calls `as_utc` | — |
| tdot `_parse_dt` | **merge** | `parse_iso_utc(v)` |
| tribe / CitySpark `_parse_utc`, Meetup `_to_aware_utc` | **merge** | `parse_iso_utc(v)` |
| CarCruiseFinder `_to_aware_utc` | **parametrise** | `parse_iso_utc(v, naive_tz=LOCAL_TZ)` |
| hc911 `_parse_dt` | **keep a thin local wrapper** for the source-specific sentinel | `dt = parse_iso_utc(v); return None if dt is None or dt.year < 1990 else dt` |

The `naive_tz` default is UTC, because four of the five string parsers and both `_as_utc` copies
use it. The time zone assumed for naive values is a real per-source parameter (CarCruiseFinder's
JSON-LD is venue-local), so it is an argument, not a separate function.

The merged parser keeps tdot's `isinstance(value, str)` guard. This is a deliberate edge-case
change for tribe, CitySpark, Meetup and CarCruiseFinder: a truthy non-string now parses as missing
instead of raising `TypeError` and failing that source's whole fetch. tribe and CitySpark already
skip an event with no parseable start and log a warning, so one bad field now costs one event
rather than the whole source. Valid string input is unaffected, so `canonical_key` is too.

hc911 changes in two ways:

- **Naive values are read as UTC instead of in the host's local zone.** The old behaviour depends
  on the host's zone, which is an accident rather than a design choice. The feed always sends `Z`
  (see `tests/fixtures/hc911_sample.json`), and the Docker image runs in UTC, so production output
  does not change.
- **The sentinel check runs on the UTC value rather than the parsed one.** That only differs for an
  offset timestamp within a few hours of 1990-01-01, which the feed never sends.

The `replace("Z", ...)` call is dropped, because Python 3.14's `fromisoformat` accepts `Z` itself.

### D3. Address joining: merge the two identical joins, leave Meetup and CarCruiseFinder

`join_address(parts: Iterable[object]) -> str | None` holds the exact tribe and CitySpark
expression. Each source keeps a small local function that selects its own fields and calls it.

The other two address builders stay separate because their output differs, and address strings are
geocode-cache keys:

- **Meetup:** it does not strip, does not filter non-strings, and falls back to the venue name.
  Moving it onto `join_address` would change addresses that have stray whitespace. That would
  cause cache misses and new Nominatim lookups.
- **CarCruiseFinder:** it cleans each part with `_clean_text` but filters on the raw part, so a part
  that cleans to `""` still adds a separator. Routing it through `join_address` would change that
  output. Keeping the quirk is cheaper than proving nothing depends on it.

### D4. HTML to text: leave all four

These stay separate because their output differs, not because of any separation rule. Their output
is stored, user-visible text, and in CarCruiseFinder's case it also feeds `canonical_key`. Making
one call another would change stored events and break de-duplication against existing rows:

- **tribe vs news:** tribe does not pre-unescape (encoded markup stays literal text) and does not
  collapse whitespace inside a text node. Moving tribe descriptions onto `strip_html` would change
  stored descriptions.
- **CarCruiseFinder vs both:** it joins text nodes with **no separator**, so
  `<b>Cars</b><i>Coffee</i>` gives `CarsCoffee`. It cleans event **titles**, so changing it would
  change `normalize_title` input and therefore `canonical_key`.
- **zoo:** it takes a node, not a string.

The differences are three independent switches (pre-unescape, separator, whitespace collapse). A
helper with three flags would be harder to read than four three-line functions.

### D5. Comma-separated settings: one `split_csv` in `config.py`, list properties for plain lists

- `split_csv(value: str) -> list[str]` is a module-level function in `app/config.py`. It splits
  on `,`, strips each entry, drops empty entries, and preserves order.
- `blocked_tags` keeps its signature and becomes `{n.lower() for n in split_csv(...)}`.
- New properties follow the same pattern: `tdot_endpoint_list`, `epb_service_list` and
  `events_ical_feed_list`, each returning `list[str]`. The tdot, epb and iCal call sites read them.
- tnaw `_parse_layers` and the tribe loop in `build_sources` call `split_csv` for the split and keep
  their own entry parsing. `Settings` owns the comma list; the consumer owns what an entry means.
  The tribe malformed-entry warning stays in `build_sources` on the `localdash.events` logger, as
  `tests/test_events_tribe.py::test_build_sources_skips_malformed_entries_loudly` expects.

**Detection timing does not change.** The review assumed that moving parsing onto `Settings` would
change when a malformed value is detected. That only happens if the parsing becomes a pydantic
`field_validator` or `computed_field`, which run when `get_settings()` constructs the object.
Properties run lazily, at the same call sites as today: collector `__init__`, and `build_sources`
once per events refresh. The only "malformed" case is the tribe entry, and it is detected and
logged exactly where it is now.

I rejected eager validators for three reasons:

- A bad tribe entry would no longer be skipped with a warning during the refresh it affects.
  Instead it would either stop startup or log a warning at import time.
- The warning would leave the `localdash.events` logger.
- `Settings` would need to know what an events entry means.

### D6. EWKT: one `ewkt_point(lat, lon)`

`ewkt_point(lat: float, lon: float) -> str` returns `f"SRID=4326;POINT({lon} {lat})"`.

- The argument order is `(lat, lon)`, matching the `Coords` tuples events already uses and the
  `center`/`haversine_miles` convention. The function swaps to WKT order internally, so callers no
  longer have to.
- Events calls `ewkt_point(*coords)` and timeseries calls `ewkt_point(obs.lat, obs.lon)`. Events
  `_point` is removed.
- The f-string is unchanged, so geometry fingerprints and stored values are identical.

### D7. News fetcher

- `_entry_raw_content(entry) -> str` returns `content[0].value`, else `summary`, else
  `description`, else `""`. `_entry_summary` and `_entry_image` both call it. The `raw or ""`
  guard in today's image path becomes redundant.
- `_article_row(feed, *, guid, url, title, summary, image_url, tags, published, now) -> dict` builds
  the 9-key row and calls `classify(title, summary, tags, feed.category)`.
  - The RSS path passes `_entry_tags(entry) if uses_feed_tags(source_slug) else []`.
  - The HTML path passes `[]`.
  - The comments explaining each tags choice stay at the call sites.
- `_fetch_html_feed(session, feed)` drops `source_slug`. Its only caller is `fetch_feed`, whose
  public signature does not change.

### D8. Keyword matching: share the mechanism, keep the tables and the result shape at the callers

```python
def keyword_matches(text: str, table: Mapping[str, Iterable[str]]) -> Iterator[str]:
    haystack = f" {text.lower()} "
    for key, keywords in table.items():
        if any(kw in haystack for kw in keywords):
            yield key
```

- **classify (tier 2):**
  `match = next(keyword_matches(f"{title} {summary}", TOPIC_KEYWORDS), None)`. If there is a
  match, return it; otherwise fall through to tier 3.
- **tagging:** `tag_text` returns `set(keyword_matches(text, TOPIC_KEYWORDS))`. `tag_event` is
  unchanged.

**Output is identical for both callers:**

- The match test (any keyword is a substring) and the iteration order (dict insertion order) are
  unchanged.
- classify's haystack `f" {title} {summary} ".lower()` equals
  `f" {(title + ' ' + summary).lower()} "`. Lower-casing the padding spaces is a no-op. Python's
  context-sensitive Final_Sigma rule looks only at cased neighbours, and a space is neither cased
  nor case-ignorable, so the result is the same whether the padding is added before or after
  `lower()`.
- The generator keeps classify's short-circuit on the first match.

The padding spaces are what let padded keywords such as `" ai "` match at the ends of the text.
The shared helper now owns that convention, so the two callers cannot drift apart on it.

**Is it worth doing?** Yes, though narrowly. It replaces two three-line loops with one four-line
function. The gain is that "a keyword table matches this text" has one definition, including the
padding convention; `classify.py`'s docstring already says its matcher is modelled on the events
tagger. The tables stay where they are, as separate vocabularies. The existing classify and tagging
tests guard the result, along with new `tests/test_text.py` cases for first-match order and for a
padded `" ai "` keyword at the start and end of the text.

### D9. Text utilities: move `strip_html` and `truncate_sentences` to `app/text.py`

`app/news/textutil.py` contains two kinds of code:

- **General-purpose:** `strip_html` and `truncate_sentences`, which work on any HTML fragment or
  string.
- **Clustering-specific:** `title_tokens`, `STOPWORDS` and `_WORD_RE`, which tokenise headlines for
  `clustering.py`.

The general-purpose pair moves to `app/text.py` unchanged, next to `keyword_matches`, along with
their private `_TextExtractor` and `_WS_RE`. `app/news/textutil.py` keeps the clustering
tokeniser. `news/fetcher.py`, `news/stories.py` and `tests/test_news_clustering.py` update their
imports. No re-export shim is left behind.

No caller outside news uses either function today, so this move does not remove a copy. I am
including it anyway, for two reasons:

- `app/text.py` exists for D8 regardless, so the general text helpers have an obvious home.
- The next events source that needs to truncate a description will find `truncate_sentences` there
  instead of writing a fourth variant.

The move does not change D4. Tribe and CarCruiseFinder keep their own HTML-to-text helpers,
because `strip_html` produces different output. The `strip_html` docstring gains one sentence
saying it pre-unescapes, so readers do not assume it can replace the BeautifulSoup variants.

The events `dedup._title_tokens` and `_STOPWORDS` are not merged with the news tokeniser: their
stopword lists and token rules differ, and `normalize_title` feeds `canonical_key`.

### Sibling changes (suggested landing order 1–13; this change is 7)

- **`relax-backend-feature-separation` (lands first; dependency)** writes the general guideline
  into `AGENTS.md` and the specs: backend packages are organisation, not boundaries, and shared
  code is preferred over copies. This change cites it and owns only the specific helpers. If that
  change also adds an `app-shell` requirement, the two ADDED requirements have different names and
  do not conflict.
- **`extract-orm-base` (3, lands earlier)** moves `Base` to `app/orm.py`, makes `alembic/env.py`
  import models explicitly, switches `pyproject.toml` to package discovery, and renames
  `app/schemas.py` to `app/diff.py`. This change touches none of those files. `app/ingest.py`,
  `app/collectors/` and `app/geojson.py` stay where they are, so every path here holds. Package
  discovery picks up the new top-level modules without a packaging edit.
- **`inject-settings-and-clock` (6, lands earlier)** passes settings values in instead of looking
  them up globally. If it already passes the endpoint, service and feed lists into constructors,
  the new `Settings` list properties are where those values come from. This change adds no global
  lookup.
- **`decompose-events-upsert` (5, lands earlier)** restructures `app/events/ingest.py`, which
  contains `_as_utc` and `_point` call sites. Expect only a mechanical rebase. This change does not
  touch `MatchSide` or the backfill.
- **`add-shared-http-client` (2)** owns the browser UA constant in `carcruisefinder.py` and the
  news `registry.py`. This change edits other lines of `carcruisefinder.py`, so they do not
  overlap.
- **`add-typed-contracts` (8, lands later)** may type the article row dicts. `_article_row` becomes
  the single place to put that type; this change keeps it returning a plain `dict`.
- **`unify-observation-geometry` (9, lands later)** reworks the EWKT point path in `app/ingest.py`.
  If it removes that path, `ewkt_point` keeps its events caller and stays.
- **`tidy-small-inconsistencies` (13)** may rename loggers. A test pins the logger name of the
  tribe warning, so whichever change lands second updates that test.

## Risks / Trade-offs

- [A silent change to a parsed timestamp shifts `canonical_key`] → The parametrised parser runs the
  same `fromisoformat` plus `astimezone` sequence. The existing source tests must pass without
  edits: CarCruiseFinder naive Eastern, Meetup offset, tdot, hc911 `Z` and sentinel, and the tribe
  and CitySpark fixtures. A new `tests/test_timeutil.py` pins naive-UTC, naive-Eastern across DST,
  offset, `Z`, empty, non-string and garbage inputs.
- [hc911 naive values are now read as UTC rather than host-local] → Accepted. The feed always sends
  `Z`, and the old behaviour depended on the host. The proposal calls this out.
- [Non-string timestamps no longer raise in four event sources] → Accepted as strictly more
  tolerant. tribe and CitySpark log the skip. Meetup and CarCruiseFinder treat the value the same
  way they already treat a missing or unparseable start.
- [The keyword matcher subtly changes a category or tag] → D8 shows the haystacks are equal and the
  order is preserved. `tests/test_news_classify.py` and `tests/test_events_tagging.py` must pass
  unchanged.
- [A reviewer expects the HTML-to-text helpers to be merged] → D4 records why their output differs,
  so the question is not reopened without the de-duplication context.
- [New shared modules become a dumping ground] → Each module is named for one concern (time,
  geometry, text) rather than "utils", and D1 records why each helper sits where it does.

## Migration Plan

Pure refactor with no schema, data or config migration. Roll back by reverting the
implementation PR.

## Open Questions

- Should hc911 keep its host-local reading of naive timestamps, for strict preservation, instead of
  moving to UTC? This design moves it to UTC (see D2). Say so in review if strict preservation
  should win.
