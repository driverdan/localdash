# Improve duplicate event detection

## Why

The events list shows duplicates: the same real-world event appears two or more times because
upstream sites publish it under slightly different titles (e.g. "Scenic City Street Machines
Sonic Cruise In" vs "Scenic City Street Machines Cruise in", "Cars and Coffee Franklin" vs
"Cars & Coffee Franklin", "Oltewah Cruise In" vs "Ooltewah Cruise In @ Cambridge Square" an hour
apart). The current de-duplication — an exact hash of the normalized title plus the UTC start
hour — can only merge listings whose titles normalize identically and whose starts fall in the
same hour bucket, so all of these slip through. Live data shows these duplicates occur *within*
a single source (duplicate upstream listings), not just across sources.

## What Changes

- Replace the single-hash de-duplication with tiered identity resolution at ingest:
  1. **Source-listing match** — a raw event whose source link (source name + source event
     id/URL) already exists for the same start day maps onto that event, making re-ingest
     stable regardless of title/time drift.
  2. **Exact canonical key** — today's normalized-title + start-hour hash, kept as the fast
     path.
  3. **Fuzzy candidate match** — same-day events starting within a small time window whose
     normalized title tokens match (subset or near-equal, with minor-typo tolerance) are
     merged **only when their locations agree** (geocoded coordinates close together, or the
     same venue/address text). Title similarity alone never merges: live data shows distinct
     franchise events ("Cars and Coffee <city>") with highly similar titles at the same hour
     in different cities.
- Fold common stopwords ("and", "at", "the", …) out of title normalization so "Cars & Coffee"
  and "Cars and Coffee" normalize identically.
- **BREAKING (schema)**: relax event link uniqueness from one link per `(event, source_name)`
  to one per `(event, source_name, source_url)`, so within-source duplicate listings keep both
  upstream URLs instead of clobbering each other on every refresh. Requires an Alembic
  migration.
- Add a post-ingest reconciliation pass that applies the same matcher to already-stored
  upcoming events and merges matches (union links and tags, backfill missing fields, keep one
  row) — this heals the duplicates already in the database and any that later become
  mergeable (e.g. after a geocode retry resolves a location), and its merge count is reported
  in refresh stats.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `events`: The "Cross-source de-duplication on ingest" requirement is replaced by a
  tiered-identity requirement covering source-listing identity, exact-key matching, the
  location-gated fuzzy match, per-listing (not per-source) links, and the reconciliation pass;
  the CarCruiseFinder "Overlap with other car-event sources merges" scenario and the refresh
  stats wording are updated to match.

## Impact

- `app/events/dedup.py` — normalization gains stopword folding; new candidate matcher
  (token-set comparison with typo tolerance, time window, location-agreement gate).
- `app/events/ingest.py` — `upsert_raw_events` gains the tiered lookup and the per-listing
  link handling; new reconciliation pass wired into the refresh cycle; refresh stats gain a
  reconciled-merge count.
- `app/events/models.py` + new Alembic migration — `event_links` unique constraint changes to
  `(event_id, source_name, source_url)`.
- `app/events/refresh.py`, `app/api/events.py` — refresh result plumbing for the new count.
- Existing rows: the five "Scenic City Street Machines" pairs, the Franklin pair, and the
  Ooltewah pair merge on the first refresh after deploy; no manual data fix needed.
- Tests: `tests/test_events_dedup.py` and `tests/test_events_ingest.py` grow matcher and
  reconciliation coverage, including the observed false-positive pairs as must-not-merge cases.
