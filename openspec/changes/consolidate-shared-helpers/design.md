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

The events gotchas in `AGENTS.md` set the constraint for this change. `canonical_key` hashes the
normalised title and the UTC start hour. Any change to how a source parses a timestamp, or how it
cleans a title, moves events to new keys and breaks cross-source de-duplication against rows
already stored. Address strings are geocode-cache keys, so changing them would cause extra
Nominatim lookups.

## Goals / Non-Goals

**Goals:**

- One implementation each of: float coercion, datetime → UTC, ISO string → UTC, EWKT point, the
  shared address join, comma-separated setting splitting, feed raw-content extraction, and the
  article row.
- Byte-identical output for every well-formed upstream value. Where a malformed-input edge case
  changes, state it.
- A written import rule for shared backend code, mirroring `frontend/src/lib/`.

**Non-Goals:**

- Merging the HTML-to-text helpers or the address builders that behave differently.
- The browser User-Agent constants and httpx clients (`add-shared-http-client`).
- The `MatchSide` and backfill duplication in `app/events/ingest.py` (`decompose-events-upsert`).
- The news `classify.py` and events `tagging.py` keyword tables, which stay separate on purpose.
- Typing the article row (`add-typed-contracts`).

## Decisions

### D1. Placement: top-level shared modules for cross-feature helpers, feature-local otherwise

A helper goes in the narrowest scope that covers all of its callers:

- **Cross-feature** (timeseries and events both call it): flat modules directly under `app/`,
  next to the existing shell modules (`config.py`, `db.py`, `redaction.py`, `ws.py`).
  - `app/timeutil.py`: `as_utc`, `parse_iso_utc`.
  - `app/geo.py`: `ewkt_point`.

  These modules import only the standard library. They **never** import from a feature package
  (`app.collectors`, `app.events`, `app.news`, `app.weather`, or the future `app.timeseries`).
  This is the backend counterpart of the `lib/` rule in `frontend-shell`.
- **One feature**: that feature's existing base module.
  - `as_float` goes in `app/collectors/base.py`, since only collectors call it.
  - `join_address` goes in `app/events/sources/base.py`, next to `clean_image_url`.
- **Settings parsing**: `app/config.py` (D5).

I rejected an `app/common/` or `app/utils/` package. Two two-function modules don't need a
package, and a generic "utils" bucket attracts unrelated code. I also rejected putting
`parse_iso_utc` in `app/collectors/base.py` and importing it from events: that would be one
feature importing another feature's internals.

`news/textutil.py` stays in news, because no other feature shares its code (D4).

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
use it. The time zone assumed for naive values is a genuine per-source parameter: CarCruiseFinder's
JSON-LD is venue-local. That makes it an argument, not a separate function.

The merged parser keeps tdot's `isinstance(value, str)` guard. This is a deliberate edge-case
change for tribe, CitySpark, Meetup and CarCruiseFinder: a truthy non-string now parses as missing
instead of raising `TypeError` and failing that source's fetch. For tribe and CitySpark, an event
with no parseable start is already skipped with a warning, so one bad field now costs one event
rather than the whole source. Valid string input is unaffected, so `canonical_key` is too.

hc911 has two differences:

- Its naive-value behaviour changes from "host local zone" to UTC. The current behaviour depends
  on the host's zone, which is an accident rather than a design choice. The feed always sends `Z`
  (see `tests/fixtures/hc911_sample.json`), and the Docker image runs in UTC, so production output
  does not change.
- The sentinel check now runs on the UTC value rather than the parsed one. That only differs for
  an offset timestamp within a few hours of 1990-01-01, which the feed never sends.

The `replace("Z", ...)` call is dropped, because Python 3.14's `fromisoformat` accepts `Z` itself.

### D3. Address joining: merge the two identical joins, leave Meetup and CarCruiseFinder

`join_address(parts: Iterable[object]) -> str | None` holds the exact tribe and CitySpark
expression. Each source keeps a small local function that selects its own fields and calls it.

- **Meetup: leave.** It doesn't strip, doesn't filter non-strings, and falls back to the venue
  name. Moving it onto `join_address` would change address strings that have stray whitespace.
  Addresses are geocode-cache keys, so that would cause cache misses and new Nominatim lookups.
- **CarCruiseFinder: leave.** It cleans each part with `_clean_text` and filters on the raw part,
  so a part that cleans to `""` still adds a separator. Routing it through `join_address` would
  change that output. Keeping the quirk is cheaper than proving nothing depends on it.

### D4. HTML to text: leave all four

All four differ in kind, and their output feeds stored, user-visible text, and in one case
`canonical_key`:

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
- tnaw `_parse_layers` and the tribe loop in `build_sources` call `split_csv` for the split. Each
  keeps its own entry parsing. Settings owns the comma list; the feature owns what an entry means.
  The tribe malformed-entry warning stays in `build_sources` on the `localdash.events` logger, as
  `tests/test_events_tribe.py::test_build_sources_skips_malformed_entries_loudly` expects.

**Detection timing is unchanged.** The review assumed that moving parsing onto `Settings` changes
when a malformed value is detected. That is only true if the parsing becomes a pydantic
`field_validator` or `computed_field`, which runs when `get_settings()` constructs the object.
Properties run lazily at the same call sites as today (collector `__init__`, and `build_sources`
once per events refresh). The only "malformed" case is the tribe entry, and it is detected and
logged exactly where it is now.

I rejected eager validators for three reasons:

- A bad tribe entry would move from "skipped with a warning" to either a startup failure or a
  warning at import time, away from the refresh it affects.
- The warning would leave the `localdash.events` logger.
- Settings would need to know the meaning of events entries.

### D6. EWKT: one `ewkt_point(lat, lon)`

`ewkt_point(lat: float, lon: float) -> str` returns `f"SRID=4326;POINT({lon} {lat})"`. The
argument order is `(lat, lon)`, matching the `Coords` tuples events already uses and the
`center`/`haversine_miles` convention. The function swaps to WKT order inside, so each call site
no longer has to. Events calls `ewkt_point(*coords)`, timeseries calls `ewkt_point(obs.lat, obs.lon)`,
and events `_point` is removed. The f-string is unchanged, so geometry fingerprints and stored
values are identical.

### D7. News fetcher

- `_entry_raw_content(entry) -> str` returns `content[0].value`, else `summary`, else
  `description`, else `""`. `_entry_summary` and `_entry_image` both call it. The current image
  path's `raw or ""` guard becomes redundant.
- `_article_row(feed, *, guid, url, title, summary, image_url, tags, published, now) -> dict` builds
  the 9-key row and calls `classify(title, summary, tags, feed.category)`. The RSS path passes
  `_entry_tags(entry) if uses_feed_tags(source_slug) else []`; the HTML path passes `[]`. The
  comments explaining each tags choice stay at the call sites.
- `_fetch_html_feed(session, feed)` drops `source_slug`. Its only caller is `fetch_feed`, whose
  public signature does not change.

### Sibling changes (suggested landing order 1–13; this change is 7)

- **`move-timeseries-into-package` (3, lands earlier)** moves `app/collectors/` and
  `app/ingest.py` under `app/timeseries/`. Implement against whatever paths exist at the time:
  `as_float` goes in the timeseries collectors' `base.py`, wherever that is. `app/timeutil.py`
  and `app/geo.py` stay at the top level as shared modules, which fits that change's intent of
  leaving only shell and shared code at the top of `app/`.
- **`inject-settings-and-clock` (6, lands earlier)** passes settings values in instead of global
  lookups. If it already passes the endpoint/service/feed lists into constructors, the new
  `Settings` list properties are where those values come from. Nothing here adds a global lookup.
- **`decompose-events-upsert` (5, lands earlier)** restructures `app/events/ingest.py`, which
  holds `_as_utc` and `_point` call sites. Expect a mechanical rebase only. This change does not
  touch `MatchSide` or the backfill.
- **`add-shared-http-client` (2)** owns the browser UA constant in `carcruisefinder.py` and the
  news `registry.py`. This change edits other lines of `carcruisefinder.py`; no overlap.
- **`add-typed-contracts` (8, lands later)** may type the article row dicts. `_article_row`
  becomes the single place to put that type; this change keeps it returning a plain `dict`.
- **`unify-observation-geometry` (9, lands later)** reworks the EWKT point path in
  `app/ingest.py`. If it removes that path, `ewkt_point` keeps its events caller and stays.
- **`tidy-small-inconsistencies` (13)** may rename loggers. The tribe warning's logger name is
  pinned by a test, so whichever change lands second updates the test.

## Risks / Trade-offs

- [Silent change to a parsed timestamp shifts `canonical_key`] → The parametrised parser runs the
  same `fromisoformat` plus `astimezone` sequence. The existing source tests (CarCruiseFinder naive
  Eastern, Meetup offset, tdot, hc911 `Z` and sentinel, tribe and CitySpark fixtures) must pass
  without edits. A new `tests/test_timeutil.py` pins naive-UTC, naive-Eastern across DST, offset,
  `Z`, empty, non-string and garbage inputs.
- [hc911 naive values now read as UTC rather than host-local] → Accepted. The feed always sends
  `Z`, and the old behaviour depended on the host. Called out in the proposal.
- [Non-string timestamps no longer raise in four event sources] → Accepted as strictly more
  tolerant. tribe and CitySpark log the skip. Meetup and CarCruiseFinder treat a missing start the
  same way they already treat a missing or unparseable one.
- [A reviewer expected the HTML-to-text helpers to be merged] → D4 records why they are not, so the
  question isn't reopened without the de-duplication context.
- [New shared modules become a dumping ground] → The import rule (stdlib only, no feature imports)
  is written into `AGENTS.md` and the `app-shell` spec. A helper qualifies only if more than one
  feature calls it.

## Migration Plan

Pure refactor with no schema, data or config migration. Roll back by reverting the
implementation PR.

## Open Questions

- Should hc911 keep its host-local reading of naive timestamps, for strict preservation, instead of
  moving to UTC? This design moves it to UTC (see D2). Say so in review if strict preservation
  should win.
