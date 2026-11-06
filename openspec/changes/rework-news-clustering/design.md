## Context

`app/news/clustering.py` holds the clustering ported from ChattNews. It compares every pair of
titles in the 7-day story window and links a pair when any one rule fires:

- token-set Jaccard ≥ 0.5
- containment ≥ 0.8
- `SequenceMatcher` ratio ≥ 0.85
- across outlets only: ≥ 3 shared "distinctive" tokens, where "common" means appearing in more
  than 5% of titles

Linked pairs are merged with union-find (single linkage). `recluster()` runs this after every
fetch and writes `cluster_id` (the smallest member id). `stories.py` groups by `cluster_id` for
the Stories API.

An explore session (Oct 31 – Nov 5, 2026) replayed this on the live DB and found three failure
modes (see proposal):

- The binary common-token cutoff treats `man`, `dies`, `police` and `school` as distinctive.
- Union-find chains separate events together through one weak link.
- There is no time limit, so follow-ups and daily recurring columns merge.

A scratch prototype of the design below was run against 14 days of real articles.

The user's constraints from that session:

- Follow-ups must not merge; a time window is the accepted mechanism.
- Same-outlet merging is acceptable.
- No LLM calls.

Relevant facts:

- Articles are never pruned (6.5k rows back to Oct 2025), so a longer lookback corpus is available.
- Chattanoogan, about 30% of articles, has no feed summaries. The other outlets have them for
  92–100% of articles.
- Story ids are used only as client list keys and are never persisted, so regrouping is safe.

## Goals / Non-Goals

**Goals:**

- Articles merge only when they report the same event, not when they merely share a topic.
- Stop chaining: no story can grow by repeatedly linking to its newest member.
- Clustering quality is measured against a labeled fixture of real articles, not judged by eye.
- Keep the existing interfaces: `recluster(session) -> int`, the `cluster_id` column, the
  story-id convention, and the Stories API shape.
- Stay deterministic, dependency-free, and fast enough to run every 15 minutes.

**Non-Goals:**

- LLM adjudication or embedding similarity. Embeddings measure topic similarity, which is exactly
  the problem being fixed.
- Fetching article pages to get text for outlets without summaries (Chattanoogan).
- Using summaries as positive evidence (a "boost"). Summaries are a veto only in this change. A
  boost was measured during implementation and did not raise recall (see D6).
- Keeping story ids stable across reclusters.
- The `db` restart policy (separate fix).

## Decisions

### D1. IDF-weighted tokens instead of a binary common/distinctive split

Each token gets weight `ln((N+1)/(df+1))`, where df is counted over a corpus of articles. A
shared `man` (df≈23 in 550 titles) then contributes about a third of what a shared `amnicola`
contributes, rather than an equal vote. Pair similarity uses weighted set measures:

- **weighted Jaccard** `W(A∩B) / W(A∪B)`
- **weighted containment** `W(A∩B) / min(W(A), W(B))`

The tokenizer keeps numeric tokens of any length (`27`, `41`, `23`), since those are often the
most event-specific part of a headline. Words still need more than 2 characters and must not be
stopwords. This changes `textutil.title_tokens`, whose only consumer is clustering.

*Alternatives:*

- Lowering the 5% cutoff: tested at 2%, it helps but is still binary and leaves borderline words
  like `lee` and `red` with full weight.
- BM25 or TF-IDF cosine: headlines are too short for term frequency to matter, so weighted set
  overlap gives the same ranking more simply.

### D2. A 30-day DF corpus, separate from the 7-day clustering window

Document frequency is computed over articles published in the last 30 days
(`IDF_LOOKBACK_DAYS = 30`). Only the 7-day story window is clustered. A longer, larger corpus
changes little from one 15-minute refresh to the next, so borderline pairs don't flip between
merged and split. Two DF tables are built from the same corpus:

- one over title tokens, for the title score
- one over title+summary tokens, for the summary veto

*Alternative:* DF over the 7-day window only, as the current code does. It's cheaper but noisier,
and a story near a threshold could flicker on the dashboard.

### D3. Pair match predicate

Articles *a* and *b* **match** when all of the following hold:

1. The title score passes, either:
   - weighted Jaccard ≥ `MATCH_JACCARD` (initial 0.35), or
   - weighted containment ≥ `MATCH_CONTAINMENT` (initial 0.45) **and** weighted Jaccard ≥
     `CONTAINMENT_JACCARD_FLOOR` (initial 0.25) **and** at least 2 shared tokens.

   The floor exists because, on its own, containment over-rewards short titles: "Latest Hamilton
   County Arrest Report" is mostly contained in a Dairy Queen story whose summary says "arrest
   report" (weighted Jaccard 0.11).
2. **Number veto.** Both titles contain numeric tokens (excluding four-digit years `19xx`/`20xx`)
   and the two sets are disjoint, e.g. `Dist. 23` vs `Dist. 24`. Shared numbers such as `9` in
   "$9.3M" and "$9.25 Million" don't trigger it.
3. **Summary veto.** If both articles have summaries of at least 40 characters, the weighted
   Jaccard of their title+summary tokens must be ≥ `SUMMARY_VETO` (initial 0.10). In the
   prototype data, DECISION 2026 pairs scored 0.05–0.21 here. True pairs with very differently
   worded summaries scored as low as 0.11 (Red Bank park) and 0.13 (airport), so the veto
   threshold sits deliberately low.
4. **Recurring-column exception.** Same outlet + identical normalized title + published more than
   12h apart means no match.

The `SequenceMatcher` fallback is dropped: identical or near-identical titles already score high
weighted Jaccard. The cross-outlet-only rule and the same-outlet guard are dropped too, because
the IDF weights and vetoes now handle formulaic series for every outlet.

All initial thresholds come from the prototype. **The final values are whatever the labeled
fixture (D6) supports**, and they are recorded as module constants.

### D4. Chronological majority-match assignment instead of union-find

Process window articles in `(published, id)` order. For each article:

1. Candidate stories are those whose earliest member was published at most `STORY_WINDOW_HOURS`
   (36) before this article.
2. An article is **eligible** for a story if it matches at least half of the story's members
   (`2 × hits ≥ len(members)`).
3. Join the eligible story with the highest match fraction. Ties go to the earlier anchor, then
   the smaller story id. With no eligible story, start a new one.

`cluster_id` = smallest member article id, as today.

Why the window counts from the *anchor*: the first article defines the event. Pairwise windows
let a chain creep forward (Mon→Tue→Wed), which is how 7 daily Arrest Reports became one story.

Why "half": in the prototype, single linkage within the window still let a thin match join, and
complete linkage (match *every* member) split real stories, because six outlets word the same
crash six different ways. Half the members is the middle ground that worked on real data.

*Alternatives:*

- Union-find with a time gate: rejected, it still chains inside the window.
- Centroid vectors per story: similar results, more machinery and harder to explain.
- Agglomerative clustering with a distance cutoff: needs a library or more code for no
  demonstrated gain.

Cost is about n × (stories in window) × (members) predicate calls. With about 550 articles,
that's comfortably sub-second, and it still runs in `asyncio.to_thread`.

### D5. Keep the pure/async split

```
assign_clusters(articles, corpus) -> {article_id: cluster_id}   # pure, offline-testable
recluster(session) -> int                                        # loads window + 30d corpus, writes ids
```

`articles` rows carry `(id, source_id, published, title, summary)`. `corpus` is an iterable of
`(title, summary)` used only for DF. Thresholds stay module constants, as they are today. Only the
existing `news_story_window_days` remains a setting. These are tuning parameters, not deployment
configuration.

### D6. A labeled fixture drives the thresholds

`tests/fixtures/news_clustering.json` holds a **contiguous real window** of about 10–14 days of
articles. Each entry has id, outlet slug, published, title and summary, plus a hand-assigned
`story` label. It has to be a full window, not a cherry-picked list of pairs, because IDF depends
on the corpus: a hand-picked set would give unrealistic weights.

Labeling starts from the union of groups proposed by the current algorithm and the prototype.
Each group is checked and corrected by hand, and every other article gets a singleton label. The
fixture must include the hard cases from the explore session:

- Lee Hwy / Chickamauga Dam / Nashville chain
- DECISION 2026 series
- Arrest Report dailies
- Red Bank grab-bag
- Mocs vs Gators
- Baylor vs Asbury
- the true positives with low title overlap: airport, Aquarium, Hwy 27, Blackford St, Red Wolves

The test computes **pairwise precision and recall** of `assign_clusters(fixture, fixture)` against
the gold labels:

- predicted-same pairs that are gold-same, over predicted-same
- gold-same pairs that are predicted-same, over gold-same

It asserts both against targets: **precision ≥ 0.85, recall ≥ 0.45**. These are regression gates
set a little below what the tuned thresholds reach, not aspirations. The current algorithm's scores
on the same fixture are recorded in the PR for comparison.

The targets were first set at precision ≥ 0.95 and recall ≥ 0.80. Implementation showed both can't
be met with title evidence plus a summary veto:

| Variant (fixture: 1,155 articles, 330 gold pairs) | Precision | Recall |
| --- | --- | --- |
| Current algorithm | 0.142 | 0.852 |
| New algorithm, prototype thresholds | 0.842 | 0.515 |
| New algorithm, tuned (floor 0.30, summary veto 0.12) | 0.897 | 0.476 |
| Best recall at precision ≥ 0.85 (480-point threshold grid) | 0.860 | 0.576 |
| Best recall anywhere on the grid | 0.740 | 0.682 |

Token normalization (stemming, abbreviations) and a summary boost did not move the frontier.
The cause is structural: 177 of the 330 gold pairs involve a Chattanoogan article, which has no
summary, so those pairs are judged on headline overlap alone. The user's complaint is wrong
merges, so tuning favors precision. The cost is that some same-event articles show as separate
stories. Focused
unit tests cover each spec scenario (number veto, summary veto, recurring column, window anchor,
majority match, determinism).

## Risks / Trade-offs

- **[Title-only pairs have a hard ceiling]** Chattanoogan has no summaries, and on short headlines
  true and false pairs overlap at weighted Jaccard of about 0.28–0.32.
  → Accept the loss of recall: about half of gold same-event pairs stay separate. The fixture's
  recall gate makes the cost visible. Fetching lead-paragraph text for summary-less outlets is the
  most promising follow-up; a summary boost was measured and did not help.
- **[Overfitting to one fortnight]** Thresholds tuned on one window may not generalize; a sports
  season or an election week shifts vocabulary.
  → The fixture spans a full contiguous window with mixed categories, including an election week.
  Thresholds are kept round and conservative. The fixture can be extended with a second window
  later without changing any code.
- **[Next-day follow-ups inside 36h may still merge]** e.g. "man in critical condition" followed
  by "man dies" 17h later. → The prototype kept these apart through wording divergence (weighted
  Jaccard 0.29, summary 0.19). Any that still merge are inside the window the user accepted.
- **[Summary veto drops a true pair]** → The threshold is set below the lowest true-pair score
  observed. Fixture recall catches a regression.
- **[Story boundary shifts at the 7-day edge]** When a story's earliest article ages out of the
  window, the next-earliest becomes the anchor. → This only affects stories more than about 5.5
  days old, and the Stories API defaults to 72h. Acceptable.
- **[Fixture holds third-party headlines/summaries]** These are public RSS excerpts already
  displayed by the app. → Store only title and feed summary (already truncated), with no article
  bodies.
- **[Story ids change on deploy]** → They are only list keys client-side, so there's no
  user-visible effect beyond regrouping.

## Migration Plan

No schema change. Deploy, and the next refresh (or `POST /api/v1/news/refresh`) reclusters the
window under the new algorithm. To roll back, revert the change; the next refresh restores the
old grouping.

## Open Questions

- Resolved: the original targets (precision ≥ 0.95, recall ≥ 0.80) were unreachable. The targets
  were lowered to precision ≥ 0.85, recall ≥ 0.45 with the user's approval; see D6.
