# Design: improve-event-dedup

## Context

De-duplication today is a single mechanism: `canonical_key = sha256(normalized_title + UTC
start day-and-hour)` (`app/events/dedup.py`), looked up as a unique column on `events`. It only
merges listings whose titles normalize to the same string and whose starts fall in the same
hour bucket.

Live data (49 events) shows the duplicates that slip through are *within-source* — upstream
sites publish the same event twice under different slugs and titles:

- "Scenic City Street Machines **Sonic** Cruise In" vs "… Cruise in" — one extra token, same
  hour, same venue ("Sonic"), five recurring date pairs.
- "Cars **and** Coffee Franklin" vs "Cars **&** Coffee Franklin" — "&" is stripped as
  punctuation but "and" survives normalization; same hour, both on Hillsboro Rd.
- "**Oltewah** Cruise In" vs "**Ooltewah** Cruise In @ Cambridge Square" — typo plus extra
  tokens, starts one hour apart (defeats the hour bucket), addresses one house number apart on
  the same street.

The same data shows why fuzzy title similarity alone cannot be the rule: "Cars and Coffee
Franklin" vs "Cars And Coffee Memphis" score 0.72 and "731 Cars and Coffee" (Humboldt) vs
"Cars N' Coffee" (Crossville) score 0.81 — distinct events in different cities at the same
hour — while the true Sonic pair scores 0.93. No similarity threshold separates them; location
must gate the match.

Two structural obstacles in the current code:

- `event_links` is unique on `(event_id, source_name)` and ingest refreshes the URL per source
  name (`app/events/ingest.py`), so merging two listings from the same source would make their
  URLs clobber each other every refresh.
- Better ingest-time matching alone cannot heal the duplicate rows already stored.

## Goals / Non-Goals

**Goals:**
- Merge duplicate listings that differ by added/dropped title words, stopword/punctuation
  variants, minor typos, or a start-time offset of up to two hours — when their locations agree.
- Never merge distinct events with similar titles (the franchise "Cars and Coffee <city>" case).
- Keep re-ingest idempotent, including for merged within-source duplicates.
- Heal duplicates already in the database without manual intervention.

**Non-Goals:**
- Cross-day matching (an event listed on different days is treated as distinct occurrences).
- Semantic/LLM or embedding-based matching; pg_trgm or other DB extensions.
- Merging events with similar titles but no location evidence — we accept residual duplicates
  there rather than risk false merges.
- Retroactive un-merging tooling.

## Decisions

### D1: Tiered identity resolution, strongest signal first

For each raw event, ingest resolves identity in order:

1. **Source-listing match**: an existing `EventLink` with the same `source_name` and the same
   `source_event_id` (falling back to `source_url` when the id is null), *and* whose event
   starts on the same UTC day as the raw event. The day gate protects against recurring-event
   feeds reusing one UID/URL across occurrences — without it, tier 1 would collapse a series
   onto one row.
2. **Exact canonical key**: today's hash lookup, unchanged. Preserves the spec'd status-quo
   merge ("Jazz Night!" vs "jazz night", same UTC hour) even when neither listing has any
   location information.
3. **Fuzzy candidate match** (D2/D3): only when tiers 1–2 miss.

*Why*: the source link is a guaranteed identity (same listing re-reported), so it must win —
it also keeps re-ingest stable after a fuzzy merge changes which row a listing lives on.
Alternative considered: dropping `canonical_key` entirely in favor of the matcher; rejected
because the unique column is a cheap fast path and keeps the no-location exact merge intact.

### D2: Token-based title matching with stopword folding and typo tolerance

- Normalization (shared with `canonical_key`): lowercase, strip punctuation, collapse
  whitespace, then drop stopword tokens (`a an and at in n of on the to with @ &`). This makes
  "Cars & Coffee Franklin" ≡ "Cars and Coffee Franklin" by construction.
- Two titles *match* when one's token multiset is a subset of the other's (covers
  added/dropped words: "… Sonic Cruise In" ⊇ "… Cruise in") or they are equal after per-token
  fuzzy comparison. Token comparison tolerates minor typos: tokens of length ≥ 5 compare equal
  at edit distance ≤ 1 ("oltewah" ≈ "ooltewah"); shorter tokens must match exactly (so
  "franklin" never matches "memphis", and numbers like "731" stay significant).
- Guard: the smaller token set must have ≥ 2 tokens, so a degenerate title like "Car show"
  cannot subset-match into everything.

*Why token subset over similarity ratio*: observed data has a false pair at 0.81 and a true
pair at 0.91 — thresholds are brittle, while subset semantics express exactly the observed
failure mode ("same title, a word added"). *Why edit distance ≤ 1 over trigram similarity*:
one observed typo case; a bounded hand-rolled check (stdlib-only, no dependency) is easy to
reason about and test.

### D3: Location agreement is a hard gate for the fuzzy tier

A fuzzy title match merges only when the candidate pair also passes **one** of, in order of
strength:

1. Both geocoded and coordinates within 0.5 miles (haversine, helper already in ingest).
2. Equal normalized venue names or equal normalized addresses (same normalization as titles),
   used only when at least one side lacks coordinates.

If neither side offers any location evidence, the fuzzy tier does **not** merge — tier 2
still covers exact-title/same-hour merges for such events.

Time gate: candidates are events starting within ±2 hours of the raw event (same UTC day
implied by the window in practice). This retires the documented hour-boundary caveat and
covers the observed 1-hour-apart Ooltewah pair, while keeping "every Saturday 9am" franchise
events from other cities out of reach of the location gate anyway.

*Why*: location is the only signal that separates the true pairs from the false pairs in
observed data. Venue-name equality is a weaker signal (chain venues like "Sonic" repeat across
cities), which is why coordinates take precedence when both sides have them and the title gate
must also pass.

### D4: Per-listing links instead of per-source links

`event_links` uniqueness changes from `(event_id, source_name)` to
`(event_id, source_name, source_url)` via a new Alembic migration (`0005_…`, hand-written raw
SQL per project convention). Ingest matches an existing link by `(source_name, source_url)`
and refreshes its `source_event_id`; a new URL from the same source appends a link.

*Why*: after a within-source merge, one event legitimately carries two upstream URLs from the
same source. Under the old rule the second URL would overwrite the first on every refresh
(URL flapping) and one listing's link would be lost. Alternative — dropping URL refresh
entirely — rejected: upstream URLs do change (slug edits) and the link should follow the
listing, keyed by `source_event_id` where available.

### D5: Post-ingest reconciliation pass heals stored duplicates

After each ingest cycle (inside the same refresh serialization, like the geocode retry pass),
a reconciliation pass loads upcoming events grouped into same-day buckets and applies the D2/D3
matcher pairwise within each bucket. Matched pairs merge:

- Survivor: earlier-created row (lowest id) — stable across runs.
- Title: the longer of the two titles (more informative; picks "Ooltewah Cruise In @ Cambridge
  Square" over the typo'd "Oltewah Cruise In").
- Union links (respecting the new uniqueness) and tags; backfill description, venue, address,
  `ends_at`, and location from the loser where the survivor lacks them; delete the loser (link
  and tag rows cascade).
- The refresh result reports the merge count (`reconciled`).

*Why a recurring pass instead of a one-time data migration*: the fuzzy logic in an Alembic
migration would be duplicated and frozen; a recurring pass heals existing rows on the first
refresh after deploy, is idempotent, and also catches pairs that only become mergeable later
(e.g. the location gate starts passing after a geocode-retry resolves coordinates). Cost is
O(n²) per same-day bucket, negligible at current volumes (tens of events per day).

## Risks / Trade-offs

- **[False merge via chain venues]** Two different events at "Sonic" in different cities with
  subset-matching titles on the same day → both title and venue gates pass. → Mitigated by
  coordinates taking precedence whenever both sides are geocoded; residual risk accepted
  (requires near-identical titles, same day ±2h, ungeocode-able addresses, and same venue
  string).
- **[False merge via typo tolerance]** Edit-distance 1 on ≥5-char tokens could equate distinct
  words (e.g. "north"/"forth"). → The full match still requires every other token to align
  plus the location gate; tests pin the observed false pairs as must-not-merge.
- **[Wrong survivor title]** "Longer title wins" may occasionally pick a worse title. →
  Cosmetic only; links preserve every upstream listing for verification.
- **[Recurring-feed UID reuse]** If a feed reuses one UID across occurrences, tier 1 without
  the day gate would merge a whole series. → Day gate in D1; covered by a test.
- **[O(n²) reconciliation]** Quadratic within a day bucket. → Bounded to upcoming events and
  same-day buckets; volumes are tens per day. Revisit only if event volume grows by orders of
  magnitude.

## Migration Plan

1. Ship migration `0005` altering the `event_links` unique constraint (downgrade restores the
   old constraint after collapsing any now-duplicate `(event_id, source_name)` rows to one).
2. Deploy; the first refresh cycle's reconciliation pass merges the existing duplicate rows
   (five Scenic City pairs, Franklin pair, Ooltewah pair).
3. Rollback: revert code and downgrade the migration. Already-merged rows stay merged — they
   were genuine duplicates, so no un-merge tooling is needed.

## Open Questions

None blocking. The 0.5-mile radius, ±2-hour window, and stopword list are constants in
`dedup.py`, chosen from observed data; tune later if new sources surface counterexamples.
