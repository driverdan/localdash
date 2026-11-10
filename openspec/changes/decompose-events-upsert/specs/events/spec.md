## MODIFIED Requirements

### Requirement: Cross-source de-duplication on ingest
Ingest SHALL collapse the same real-world event — whether reported by different sources or
listed more than once by a single source — onto one canonical record, resolving identity in
tiers, strongest signal first:

1. **Source-listing identity**: a raw event SHALL map onto the existing event that already
   carries a link with the same source name and the same source event id (falling back to the
   source URL when the id is absent), provided that event starts on the same UTC day as the
   raw event. A matching listing whose stored event starts on a different UTC day SHALL NOT
   match this tier (recurring feeds may reuse one id across occurrences).
2. **Exact canonical key**: otherwise, a stable hash of the normalized title plus the UTC
   start day-and-hour, as today. Title normalization SHALL lowercase, strip punctuation,
   collapse whitespace, and fold out common stopword tokens (at minimum "a", "an", "and",
   "at", "in", "n", "of", "on", "the", "to", "with"), so variants such as "Cars & Coffee
   Franklin" and "Cars and Coffee Franklin" normalize identically.
3. **Location-gated fuzzy match**: otherwise, the raw event SHALL merge into a stored event
   when all of the following hold:
   - the stored event starts within 2 hours of the raw event;
   - their normalized title token sets match: one is a subset of the other, or they are equal
     — where individual tokens of at least 5 characters compare equal at edit distance ≤ 1
     (tolerating minor typos such as "Oltewah"/"Ooltewah") and shorter tokens must be
     identical — and the smaller token set has at least 2 tokens;
   - their locations agree: both are geocoded and lie within 0.5 miles of each other, or —
     only when at least one side lacks coordinates — their normalized venue names or
     normalized addresses are equal.
   Title similarity alone SHALL NOT merge events: a fuzzy candidate pair with no location
   evidence on either side, or with locations that disagree, SHALL remain separate events.

New identities create an event unless dropped by the ingest radius filter; matches merge.
Every merge — an incoming report merged at ingest, or a stored row merged by the reconciliation
pass below — SHALL apply one shared backfill rule to the same field set: an empty description,
and a null venue name, address, end time, or image URL, is filled from the absorbed record when
that record has a value; a value already present is never overwritten. Location is the one
field each path handles separately: at ingest a still-unlocated event takes the report's
supplied coordinates, or else is geocoded from its (possibly just backfilled) address. Each distinct
upstream listing SHALL contribute one link per event, unique per
`(event, source_name, source_url)` — so an event merged from two listings of the same source
keeps both URLs — with the link matched by source name and URL on re-ingest (refreshing its
source event id) rather than replaced. A failure in one source SHALL NOT abort ingestion of
the others.

After each ingest cycle, and under the same refresh serialization, a reconciliation pass
SHALL compare stored upcoming events within the same UTC day pairwise and merge a pair when
their canonical keys — recomputed under the current normalization, since stored keys predate
normalization changes — are equal (the same evidence that merges fresh reports at tier 2), or
when the tier-3 matcher accepts the pair. On a merge the earlier-created row survives, the longer title is kept, links
and tags are unioned, the shared backfill rule above is applied from the removed row, a
missing location is copied from the removed row, and the removed row is deleted. The pass SHALL be
idempotent and its merge count SHALL be reported in the refresh result, so duplicates already
stored before this capability — or pairs that only become mergeable later (e.g. once a
geocode retry resolves coordinates) — heal without manual intervention.

#### Scenario: Same event from two sources merges
- **WHEN** two sources report "Jazz Night!" and "jazz night" with start times in the same UTC hour
- **THEN** one event row exists with two links, one per source

#### Scenario: Within-source duplicate listings merge
- **WHEN** one source lists "Scenic City Street Machines Sonic Cruise In" and "Scenic City
  Street Machines Cruise in" at the same start time with the same venue name, under different
  source URLs
- **THEN** one event row exists carrying both listings' links (same source name, two URLs)

#### Scenario: Stopword and punctuation variants merge exactly
- **WHEN** "Cars & Coffee Franklin" and "Cars and Coffee Franklin" are reported with start
  times in the same UTC hour
- **THEN** they normalize to the same canonical key and one event row exists

#### Scenario: Typo and extra words merge across an hour boundary when locations agree
- **WHEN** "Oltewah Cruise In" and "Ooltewah Cruise In @ Cambridge Square" are reported one
  hour apart with addresses that geocode within half a mile of each other
- **THEN** one event row exists

#### Scenario: Similar franchise titles in different cities stay separate
- **WHEN** "Cars and Coffee Franklin" and "Cars And Coffee Memphis" are reported at the same
  hour with addresses geocoding roughly 200 miles apart
- **THEN** two separate event rows exist

#### Scenario: Fuzzy title match without location evidence stays separate
- **WHEN** two listings with token-subset titles start within 2 hours but neither carries
  coordinates, a venue name, or an address in common
- **THEN** two separate event rows exist

#### Scenario: Recurring listing id does not collapse a series
- **WHEN** a feed reuses one source event id for occurrences of the same event on different
  days
- **THEN** each day's occurrence is a separate event, each linking that id

#### Scenario: Merge backfills missing fields
- **WHEN** an event was stored without an address and a second source reports it with one
- **THEN** the canonical event gains the address and is geocoded from it

#### Scenario: Ingest and reconciliation backfill the same fields
- **WHEN** a stored event is missing its description, venue name, address, end time, and image
  URL, and it absorbs another record that has all five — once as an incoming report merged at
  ingest, and once as a duplicate row merged by the reconciliation pass
- **THEN** in both cases the surviving event gains all five values
- **AND** any of those fields the surviving event already had keeps its stored value

#### Scenario: One failing source does not abort the cycle
- **WHEN** one registered source raises during fetch
- **THEN** events from the remaining sources are still ingested

#### Scenario: Repeat ingest is idempotent
- **WHEN** the same source reports the same events on consecutive cycles
- **THEN** no duplicate events or links are created, including for events previously merged
  from multiple listings

#### Scenario: Reconciliation heals stored duplicates
- **WHEN** two stored upcoming events on the same day satisfy the fuzzy matcher (e.g. rows
  created before this capability deployed) and a refresh cycle runs
- **THEN** after the cycle one merged row remains — carrying both rows' links and tags and
  the longer title — and the refresh result counts the merge

#### Scenario: Reconciliation merges pairs that become mergeable later
- **WHEN** two stored same-day events with matching titles were kept separate for lack of
  location evidence and a later geocode resolves their addresses to within half a mile
- **THEN** the next refresh cycle's reconciliation pass merges them

#### Scenario: Reconciliation merges stale-key exact duplicates
- **WHEN** two stored events' titles normalize identically under the current normalization
  with starts in the same UTC hour, but their stored canonical keys predate that
  normalization and their locations do not agree (e.g. one address geocoded imprecisely)
- **THEN** the reconciliation pass merges them on recomputed key equality alone
