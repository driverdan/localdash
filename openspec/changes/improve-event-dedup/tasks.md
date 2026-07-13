# Tasks: improve-event-dedup

## 1. Matcher (dedup.py)

- [ ] 1.1 Add stopword folding to `normalize_title` (drop `a an and at in n of on the to
      with` tokens after punctuation stripping) and keep `canonical_key` building on it;
      update existing dedup tests for the new normalization
- [ ] 1.2 Add a token-comparison helper: tokens ≥ 5 chars equal at edit distance ≤ 1,
      shorter tokens exact (stdlib-only bounded edit-distance check)
- [ ] 1.3 Add `titles_match(a, b)`: normalized token sets equal or one a subset of the other
      under the fuzzy token comparison, requiring the smaller set to have ≥ 2 tokens
- [ ] 1.4 Add `events_match(...)` combining the ±2 h start-time window, `titles_match`, and
      the location gate (coords within 0.5 mi when both present; else equal normalized venue
      name or address when at least one side lacks coords; no location evidence → no match)
- [ ] 1.5 Unit tests in `tests/test_events_dedup.py` pinning the observed pairs: Sonic pair
      merges, Franklin `&`/`and` pair normalizes equal, Ooltewah typo pair matches across the
      hour boundary; Franklin-vs-Memphis and 731/Cars-N'-Coffee false pairs must NOT match;
      no-location fuzzy pair must NOT match; "Car show" single-token guard

## 2. Link schema (per-listing links)

- [ ] 2.1 Alembic migration `0005`: drop `uq_event_link_source`, add unique
      `(event_id, source_name, source_url)`; downgrade collapses duplicate
      `(event_id, source_name)` rows to one before restoring the old constraint
- [ ] 2.2 Update `EventLink.__table_args__` in `app/events/models.py` to match
- [ ] 2.3 In `upsert_raw_events`, match existing links by `(source_name, source_url)` and
      refresh `source_event_id`; append a new link for a new URL from the same source

## 3. Tiered resolution in ingest

- [ ] 3.1 Tier 1: look up an existing event via `EventLink` by `(source_name,
      source_event_id)` (fallback `source_url`), gated on same UTC start day
- [ ] 3.2 Tier 3: when the canonical-key lookup misses, query events starting within ±2 h and
      merge into the first `events_match` candidate; only then create a new event (radius
      filter unchanged, merge path stays exempt)
- [ ] 3.3 Ingest tests in `tests/test_events_ingest.py`: within-source duplicate listings
      merge into one event with two links (both URLs kept across a repeat ingest); recurring
      source-event-id on different days stays separate; fuzzy merge respects the location
      gate; repeat ingest of merged events is idempotent

## 4. Reconciliation pass

- [ ] 4.1 Add `reconcile_events(session)` to `app/events/ingest.py`: load upcoming events
      (with links/tags eagerly), bucket by UTC day, apply `events_match` pairwise; merge —
      earlier-created row survives, longer title kept, links/tags unioned, missing fields
      (description, venue, address, ends_at, location) backfilled, loser deleted; return merge
      count
- [ ] 4.2 Run the pass after ingest in the refresh cycle (`app/events/refresh.py`), inside
      the existing serialization, and surface `reconciled` in the refresh result alongside
      created/merged/skipped_far (API response included)
- [ ] 4.3 Tests: pre-seeded duplicate rows (Scenic City shape) merge on a refresh; pass is
      idempotent (second run reconciles 0); a pair kept separate for lack of location merges
      after coordinates appear; title/link/tag merge semantics verified

## 5. Verification

- [ ] 5.1 Run the full test suite
- [ ] 5.2 Rebuild the stack (`sg docker -c 'docker compose up --build -d'`), run
      `alembic upgrade head`, trigger `POST /api/v1/events/refresh`, and confirm against the
      live DB that the known duplicate pairs (5× Scenic City, Franklin, Ooltewah) collapsed
      and the events list shows no duplicates
- [ ] 5.3 Update `openspec/specs/events/spec.md` sync via `/opsx:sync` (or archive flow) once
      implementation is verified
