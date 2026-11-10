## Context

`app/events/ingest.py` on `main` (line numbers as of this proposal):

- `upsert_raw_events` (161-286): one `for raw in raws` body that does the following in order:
  1. Computes `key = canonical_key(...)`.
  2. Tier 1, `_find_by_source_listing`. On a hit whose stored key has drifted, it adopts the new
     key unless another event already holds it.
  3. Tier 2, an exact `canonical_key` lookup.
  4. Only if both miss: coordinates (supplied, else geocoded from `raw.address`), then tier 3,
     `_find_fuzzy_candidate`.
  5. On a miss: the radius check (`get_settings().center`, `continue` when too far), then
     `Event(...)`, `session.add`, and tags (supplied tags lowercased, else keyword tags, minus
     the blocklist, attached in sorted order).
  6. On a hit: the five-field backfill, then location (supplied coordinates, else geocode
     `event.address or raw.address`).
  7. The link upsert: match on `(source_name, source_url)`, append if missing, otherwise refresh
     `source_event_id` when the report has one.
  8. `session.flush()` per raw. One `commit()` at the end.

  Ruff measures C901 = 22, PLR0912 = 23, PLR0915 = 63. The repo's ruff config does not select
  these rules today. Choosing whether to enforce them belongs to `tighten-python-tooling`.
- `_merge_pair` (289-312): longer title, the same five-field backfill as step 6 (field for field,
  with the same "falsy description / `None` other field, truthy source" tests), copies the
  location if missing, unions links by `(source_name, source_url)`, unions tags. C901 = 12.
- `reconcile_events` (315-379): buckets upcoming events by UTC day as `[event, coords, key]`
  lists, compares pairs `i < j`, and tombstones merged-away rows with `bucket[j][0] = None`.
  After a merge, the survivor's local `s_coords` and `s_key` are updated so later comparisons
  use the merged state. The writes back into `bucket[i][1]` and `bucket[i][2]` are never read
  again (only `j > i` entries are read afterwards), so they are dead stores.
- `MatchSide(...)` is built by hand at 141-147 (raw side), 149-155, 351-357 and 358-364 (event
  side). `(lat, lon) if lat is not None else None` appears at 88 (as
  `row.latitude`/`row.longitude`), 152 and 338.

The review findings in the brief are accurate. Two details matter for the fix:

- The two backfill blocks are equivalent in rule, but they read different attribute names
  (`raw.end_time` vs `loser.ends_at`) and treat location differently (geocode vs copy). Only the
  five fields can be shared. Location stays per path.
- Drifted-key adoption happens on a tier-1 hit, not inside tier 2. It belongs with tier 1.

Safety net: `tests/test_events_ingest.py` (824 lines), `tests/test_events_dedup.py` (pure
matcher) and `tests/test_api_events.py` (refresh endpoint counts, including `reconciled`). They
cover the tiers, the radius filter, supplied coordinates and tags, the blocklist, image backfill,
and the three reconciliation scenarios. They do **not** pin down the cases listed under
"Characterization tests first" below.

## Goals / Non-Goals

**Goals:**
- `upsert_raw_events` reads as the tier sequence. Each concern lives in one named helper, and
  `upsert_raw_events` and `_merge_pair` drop under ruff's default C901 threshold (10) and the
  PLR0912/PLR0915 limits.
- The five-field backfill rule exists once and serves both merge paths.
- `reconcile_events` has no positional lists, no index writes, and no `None` tombstones.
- Behaviour is identical: same tiers in the same order, same geocoder calls (count, order, and
  address), same radius exemptions, same tag set and attach order, same link semantics, same
  stats dict, same log messages, same commit and flush points.

**Non-Goals:**
- The `get_settings()` calls at lines 60, 180 and 206, and a `now` parameter for
  `reconcile_events`, belong to `inject-settings-and-clock`.
- The duplicate `_as_utc` and `_point` helpers (and any EWKT or coordinate helpers shared with
  the timeseries side) belong to `consolidate-shared-helpers`.
- Typing the `{"created", "merged", "skipped_far"}` stats dict belongs to `add-typed-contracts`.
  This change keeps plain `int` counters and returns the same dict literal.
- Enabling C901/PLR rules in `pyproject.toml` belongs to `tighten-python-tooling`.
- Changes to `app/events/dedup.py`, the query shapes, or performance. N+1 lookups per raw stay
  as they are.

## Decisions

### 1. The loop body becomes a sequence of helpers

Target shape (names are indicative; the implementer may adjust them if the structure holds):

```python
for raw in raws:
    key = canonical_key(raw.title, raw.start_time)
    event = await _find_known_event(session, raw, key)        # tier 1 (+ key adoption), tier 2
    coords: Coords | None = None
    if event is None:
        coords = await _locate(session, geocoder, raw, raw.address, geo_cache)
        event = await _find_fuzzy_candidate(session, raw, coords)  # tier 3, unchanged
    if event is None:
        if _beyond_radius(raw, coords, max_miles):          # logs, keeps get_settings().center
            skipped_far += 1
            continue
        event = await _create_event(session, raw, key, coords, blocked_tags, tag_cache)
        created += 1
    else:
        await _merge_report(session, event, raw, geocoder, geo_cache)
        merged += 1
    _upsert_link(event, raw)
    await session.flush()
```

- `_find_known_event`: tier 1 via the existing `_find_by_source_listing`, the drifted-key
  adoption (including the "key already taken" guard), then the tier-2 select. It is kept
  separate from tier 3 because tier 3 needs coordinates, and those must only be computed (and
  the geocoder only called) when tiers 1-2 miss. Folding all three tiers into one
  `_resolve_identity` that returns `(event, coords)` was considered. It hides the fact that
  `coords` is only meaningful on the miss path, so it was rejected.
- `_locate(session, geocoder, raw, address, geo_cache)`: `_supplied_coords(raw)`, else
  `_geocode(..., address, ...)`. It replaces the two copies of that pattern (199-201 and
  255-259). The caller passes the address explicitly because the two sites differ: `raw.address`
  on the new-event path, `event.address or raw.address` on the merge path, read after the
  backfill.
- `_beyond_radius`: returns whether the event is dropped, and emits the same debug log. It keeps
  the `get_settings().center` lookup exactly as today, so `inject-settings-and-clock` has one
  obvious place to change.
- `_create_event`: builds and `session.add`s the `Event`, then attaches tags. The order
  "`session.add` before any tag lookup" is preserved on purpose: `_get_or_create_tag` runs
  SELECTs that autoflush. Tag-name derivation moves to a pure `_tag_names(raw, blocked_tags)`
  (supplied-lowercased, else `tag_event`, minus the blocklist). Attachment iterates
  `sorted(names)` as today.
- `_merge_report`: `_backfill_missing(event, <raw fields>)`, then the location backfill through
  `_locate` when `event.location is None`, in that order (the geocode address depends on the
  backfilled `event.address`).
- `_upsert_link(event, raw)`: synchronous. The existing link-matching and id-refresh logic moves
  over unchanged.
- `blocked_tags = get_settings().blocked_tags` stays read once per batch at the top of
  `upsert_raw_events` and is passed down as a parameter.

### 2. One backfill rule, keyword arguments for the source values

```python
def _backfill_missing(
    event: Event, *, description, venue_name, address, ends_at, image_url
) -> None:
```

It fills `description` when `not event.description` and the value is truthy, and each other
field when it is `None` and the value is truthy, exactly as both blocks do today. The ingest
merge passes `raw.description, raw.venue_name, raw.address, raw.end_time, raw.image_url`.
`_merge_pair` passes the loser's fields. Keyword arguments are used rather than a duck-typed
"source" object because `RawEvent` and `Event` name the end time differently, and an explicit
call site shows the mapping. A field-name table driven by `getattr`/`setattr` was rejected
because it hides the fields from type checkers and grep.

Location is deliberately left out of the helper. Ingest geocodes; reconciliation copies the
loser's stored point. `_merge_pair` keeps its title rule and gains `_union_links` /
`_union_tags`-style helpers only if that is needed to get under the complexity threshold.

### 3. `MatchSide` builders and the coordinate tuple

`_event_side(event, coords) -> MatchSide` replaces the three event-side constructions. The one
raw-side construction in `_find_fuzzy_candidate` stays inline, or becomes `_raw_side(raw,
coords)` if the implementer prefers symmetry. `_coords(lat, lon) -> Coords | None` replaces the
three `... if lat is not None else None` expressions, including the `GeocodeCache` read in
`_geocode`. The builders live in `ingest.py`, not as `MatchSide` classmethods in `dedup.py`,
because `dedup.py` is a pure module with no ORM imports, and it should stay that way.

`consolidate-shared-helpers` may later move `_coords` alongside the point and EWKT helpers it
unifies. That is fine; this change only names it.

### 4. Reconciliation: a dataclass and partitioning instead of tombstones

```python
@dataclass
class _Candidate:
    event: Event
    coords: Coords | None
    key: str          # canonical_key recomputed under the current normalization
```

Each day bucket is processed by `_reconcile_bucket(session, candidates) -> int`:

```python
remaining = candidates            # in Event.id order, as loaded
while remaining:
    survivor, *rest = remaining
    remaining = []
    for other in rest:            # same order as today's j loop
        if survivor.key != other.key and not events_match(...):
            remaining.append(other)
            continue
        log.info(...); _merge_pair(survivor.event, other.event)
        if survivor.coords is None and other.coords is not None:
            survivor.coords = other.coords
        survivor.key = canonical_key(survivor.event.title, survivor.event.starts_at)
        await session.delete(other.event); merged += 1
```

This is equivalent to today's algorithm. The survivor is the earliest unmerged row. It is
compared with every later unmerged row in id order, and its title, coordinates and key evolve
as it absorbs rows. Rows it does not absorb become the next round's candidates in their
original order. Merged rows simply drop out, so neither tombstones nor the dead `bucket[i][...]`
stores are needed. A `merged_away: bool` flag on the dataclass was considered. It keeps the
index loops but still needs a skip check in two places, so partitioning was preferred. The
`events_match` arguments come from `_event_side(candidate.event, candidate.coords)`, rebuilt
for every comparison as today, because the survivor's title can change mid-bucket.

### 5. Characterization tests first

Before moving any code, add tests to `tests/test_events_ingest.py` that pass on unmodified
`main` and pin down behaviour the suite does not cover today:

1. **Drifted-key adoption.** After a retitled re-report matched on tier 1, the stored
   `canonical_key` equals the new key. A companion case: when another event already holds the
   new key, the stored key is left unchanged and no new event or IntegrityError appears.
2. **Link id refresh.** Re-reporting the same `(source_name, source_url)` with a different
   `source_event_id` updates the existing link and adds none. A re-report with no
   `source_event_id` leaves the stored id as it is.
3. **Ingest merge never overwrites.** A stored event with description, venue, address and
   end time keeps all four when a matching report carries different values. An empty-string
   stored description is backfilled.
4. **Merge-path geocode uses the stored address.** A stored event that has an address but no
   location, merged with a report that has neither address nor coordinates, is geocoded from the
   stored address (assert on `FakeGeocoder.calls`).
5. **Reconciliation backfill and tag union.** The survivor gains the loser's description, venue,
   address, end time, image URL and location when its own are missing, keeps its own when
   present, and ends with the union of both rows' tags.
6. **Reconciliation chain within one bucket.** Three same-day rows where the survivor matches
   the third row only through state gained from the second: coordinates inherited from the
   second row (the location gate) or the longer title adopted from it. This guards the
   survivor-state updates that the dataclass rewrite touches. Seed with `upcoming()`.

`_merge_pair` and `_backfill_missing` do not get pure unit tests of their own. The
DB-backed behaviour tests above are the contract, and they survive later renames.

### 6. Landing order with siblings

The suggested order puts this change before `inject-settings-and-clock` (6) and
`consolidate-shared-helpers` (7). Keep it that way:

- `inject-settings-and-clock` then edits named helpers (`_beyond_radius` for the center, the
  `blocked_tags` parameter that is already threaded through, `reconcile_events` for `now`)
  instead of the 120-line loop.
- `consolidate-shared-helpers` replaces `_as_utc` and `_point` imports. This change does not
  touch them, so whichever lands second has only a trivial rebase.
- `unify-refresh-orchestration` (4) calls `run_sources` and `reconcile_events`, whose signatures
  this change keeps.
- `add-typed-contracts` (8) types the returned stats. This change leaves the dict literal for it.
- `tighten-python-tooling` (11) may enable C901/PLR09xx. After this change `ingest.py` should
  not need `noqa` comments for them.

If `inject-settings-and-clock` lands first anyway, this change rebases onto its injected
parameters. No design decision depends on the order.

## Risks / Trade-offs

- [A helper subtly reorders session operations: autoflush before `session.add`, a geocode
  before tiers 1-2 miss, location computed before the backfill] → The order constraints are
  listed in Decision 1 and checked in review. Test 4 and the existing
  `test_geocoder_called_once_per_address_within_a_run` /
  `test_supplied_coordinates_skip_geocoder_and_cache` assert on geocoder calls.
- [The partitioned reconcile loop diverges from the index loop in a multi-row bucket] →
  Characterization test 6 and the three existing reconcile tests. The equivalence argument is
  in Decision 4.
- [Characterization tests encode current behaviour that may be a bug] → They are written to
  describe `main` as it is. Behaviour that looks wrong is reported as a follow-up, not fixed
  here.
- [More functions mean more to scan in a 440-line file] → Helpers stay private, sit next to
  their callers, and each has a one-line docstring tying it to a tier or rule from the spec.
- [Merge conflicts with `inject-settings-and-clock` and `consolidate-shared-helpers`] → See the
  landing order above. The `get_settings()` call sites and `_as_utc` / `_point` are left
  textually intact so the sibling diffs stay small.

## Migration Plan

Pure code refactor with no schema, config, or data migration. Rollback is a revert of the
implementation PR. The characterization tests can stay after a revert because they pass on
`main`.

## Open Questions

- None blocking. The helper names in Decision 1 are suggestions. Review should focus on the
  boundaries (tiers 1-2 vs tier 3, location outside the backfill helper, partitioning vs a
  flag).
