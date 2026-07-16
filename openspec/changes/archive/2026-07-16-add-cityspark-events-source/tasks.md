## 1. Extend the source contract

- [x] 1.1 Add optional `latitude: float | None` and `longitude: float | None` to `RawEvent`
      (`app/events/sources/base.py`), defaulting to `None`.
- [x] 1.2 Add optional `tags: list[str]` to `RawEvent`, defaulting to an empty list (use a safe
      default — no mutable default argument).
- [x] 1.3 Update the `RawEvent` docstring: it currently states coordinates are always derived by the
      geocoder. Replace with the new rule — a source supplies what it knows; the pipeline derives
      only what is omitted.
- [x] 1.4 Update the stale convention note in `app/events/sources/meetup.py:9` ("only an address is
      emitted per event; coordinates are derived later") so it describes Meetup's own choice rather
      than a pipeline-wide rule. Do not otherwise change `MeetupSource`.

## 2. Teach ingest to prefer what the source supplied

- [x] 2.1 In `run_sources()` (`app/events/ingest.py`, near the existing `_geocode(...)` call), use
      `raw.latitude`/`raw.longitude` when both are present and call `_geocode()` only when they are
      not. An event with supplied coordinates must not touch the geocode cache.
- [x] 2.2 Where new events are tagged, use `raw.tags` when non-empty and call `tag_event()` only when
      empty.
- [x] 2.3 Lowercase source-supplied tag names before lookup/insert so they merge with the existing
      keyword vocabulary (`"Music"` → `music`).
- [x] 2.4 Confirm tag row creation stays idempotent/race-safe (on-conflict-do-nothing) with the
      larger, more varied vocabulary now flowing in.

## 3. CitySpark source

- [x] 3.1 Add settings to `app/config.py`: enable flag, portal slug + `ppid`, radius miles
      (default 25), lookahead days (default 14). Follow existing `events_*` naming.
- [x] 3.2 Create `app/events/sources/cityspark.py` with a module docstring recording: the API is
      undocumented and internal to a commercial aggregator (read via The Pulse's `ppid 9824`); no
      auth/referer/UA-spoofing is needed or used; and — prominently — that `DateStart`/`DateEnd`
      carry a lying `Z` and `StartUTC`/`EndUTC` are the only correct time fields.
- [x] 3.3 Implement a **pure** parse function over a payload dict: build the `AllTags` id→node map
      (`{id, name, parent}`), then map each event to a `RawEvent` (Name, Description, Venue, address
      from Address/CityState/Zip, `latitude`/`longitude`, `StartUTC`/`EndUTC`, rolled-up tag names,
      `Id` as `source_event_id`, a URL from `PrimaryUrl`/`Links`/`TicketUrl`).
- [x] 3.4 Implement the depth-1 tag rollup in the parse function: walk each tag id to its root and
      take the node one level below it; a root resolves to itself; de-duplicate names within an
      event (`Live Music` + `MusicEvent` → one `music`).
- [x] 3.5 Harden the parse function: skip events with no `StartUTC` (log a warning; never fall back
      to `DateStart`), skip tag ids absent from the vocabulary without dropping the event, and guard
      the rollup walk with a seen-set so a malformed parent cycle terminates instead of hanging (a
      dangling parent resolves to the deepest reachable node).
- [x] 3.6 Implement `CitySparkSource.fetch()`: POST the documented body with `end` always set,
      paginate `skip` by 100 until a page returns <100, apply a bounded page cap, and de-duplicate
      by event `Id` across pages.
- [x] 3.7 Register the source in `build_sources()` (`app/events/sources/__init__.py`) behind its
      enable setting, and update that module's docstring to list it.

## 4. Tests

- [x] 4.1 Capture a trimmed CitySpark payload fixture (a handful of events plus the tag vocabulary
      slice they reference) under `tests/`. The vocabulary slice MUST carry enough depth to exercise
      the rollup: at least one ≥3-level chain (`Performing Arts > Music > Live Music`), a second
      leaf under that same depth-1 node (`MusicEvent`) to prove collapsing, and a bare root
      (`Nightlife`). No network in tests.
- [x] 4.2 Test `StartUTC` is used and `DateStart` ignored — assert the 4-hour trap directly
      (`DateStart 08:00:00Z` + `StartUTC 12:00:00Z` → `12:00:00+00:00`).
- [x] 4.3 Test an event with no `StartUTC` is skipped and does not abort the parse.
- [x] 4.4 Test the depth-1 rollup: `Live Music` → `music` (asserting it is neither `live music` nor
      `performing arts`), a root tag resolves to itself (`Nightlife` → `nightlife`), two leaves under
      one depth-1 node collapse to a single `music` tag, an unmappable id is skipped while the event
      survives, and a cyclic parent chain terminates rather than hanging.
- [x] 4.5 Test pagination terminates on a short page, dedupes by `Id`, and that an empty result
      yields zero events without error.
- [x] 4.6 Test coordinate passthrough in ingest: a `RawEvent` with coordinates is stored at them and
      triggers no geocoder call (assert against a fake/Null geocoder).
- [x] 4.7 Test supplied tags replace keyword tagging, and that `"Music"` merges onto the existing
      lowercase `music` tag rather than creating a second row.
- [x] 4.8 Test backward compatibility: a `RawEvent` with neither coordinates nor tags still geocodes
      and keyword-tags exactly as before.
- [x] 4.9 Test a failing CitySpark source does not abort the refresh cycle, and that the source is
      absent from the registry when disabled.

## 5. Verify and document

- [x] 5.1 Run `pytest`, `ruff check` / `ruff format`, and confirm the DB-backed tests execute
      (`docker compose up -d db` + `alembic upgrade head`) rather than auto-skipping.
- [x] 5.2 Run a real refresh against a live DB and confirm: events land with locations, tags come
      from CitySpark, and Nominatim traffic for them is zero.
- [x] 5.3 Update the events section of `AGENTS.md` — add CitySpark to the sources list and record
      the `StartUTC` trap and the supplied-coords/tags rule alongside the existing feed gotchas.
- [x] 5.4 Confirm all tasks are checked off and `openspec status --change add-cityspark-events-source`
      reports complete.
