## Why

News story clustering often merges articles that share a topic but cover different events. Over
14 days of real data (847 articles), the clustering ported from ChattNews produced 98 multi-article
stories holding 343 articles. The largest had 30 articles. One 13-article "story" combined a Lee
Hwy pedestrian strike, the Chickamauga Dam police shooting, a Nashville prison death and a
Nashville bar chokehold. Three failures cause this:

1. **Generic words count as distinctive.** The binary "common token" cutoff (>5% of titles) marks
   only `chattanooga`, `county` and `tennessee` as common. Words like `man`, `dies`, `police`,
   `school` and `win` count as much as a street name, and the 3-distinctive-tokens rule fired on
   113 of 218 matching pairs.
2. **Union-find chaining.** One weak pairwise link is enough to join two complete stories.
3. **No time limit.** Articles days apart merge, so follow-ups and recurring columns (daily
   "Latest Hamilton County Arrest Report") pile into one story.

A scratch prototype of the approach below brought that 14-day window to 96 stories holding 224
articles, with a largest story of 6 (one crash covered by six outlets), and no topic chains.

## What Changes

- **BREAKING (behavior)**: Replace the ported ChattNews algorithm (token Jaccard/containment,
  SequenceMatcher fallback, cross-outlet distinctive-token rule, union-find) with an IDF-weighted,
  time-anchored clustering algorithm. The `cluster_id` column, the story-id convention (smallest
  member article id), and the Stories API shape are unchanged. Only which articles share a story
  changes.
- Weight title tokens by inverse document frequency over a lookback corpus instead of a binary
  common/distinctive split. Keep numeric tokens (`27`, `41`, `23`), which the current tokenizer
  drops.
- Add a **story time window**: an article can join a story only if it was published within 36h of
  that story's earliest article. Follow-up reports outside the window start a new story.
- Replace single-linkage union-find with **chronological assignment**: an article joins an
  existing story only if it matches at least half of that story's members.
- Add **vetoes** for formulaic series: a pair doesn't merge when both titles carry numbers and
  share none (years excluded), or when both articles have summaries and the summaries share
  almost nothing.
- Allow **same-outlet merges** under the same rules as cross-outlet ones. Drop the cross-outlet-only
  rule and the same-outlet guard. Add one narrow exception: identical titles from the same outlet
  published more than 12h apart are a recurring column and never merge.
- Add a **labeled fixture** of real articles with hand-assigned story groupings. Tests measure
  pairwise precision and recall on it, so thresholds are tuned against data.
- No LLM calls, no embedding models, no new runtime dependencies.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `news`: the "Cross-outlet story clustering" requirement is rewritten to cover IDF-weighted
  similarity, the 36h story window anchored to the earliest article, majority-match assignment,
  the number and summary vetoes, same-outlet merging, and the recurring-column exception.

## Impact

- **Code**: `app/news/clustering.py` (rewritten), `app/news/textutil.py` (numeric tokens in the
  clustering tokenizer). `recluster()` keeps its signature and stays the only call site from
  `app/news/refresh.py`.
- **Tests**: `tests/test_news_clustering.py` rewritten around the new rules, plus a new fixture
  file under `tests/fixtures/` with the labeled articles.
- **Data**: no migration. Clusters are recomputed on every refresh, so the first refresh after
  deploy regroups the 7-day window. Story ids change for regrouped stories, which affects only
  transient client state (story ids are not persisted anywhere).
- **API / frontend**: no contract change. Stories get smaller and more numerous.
- **Dependencies**: none.
- **Out of scope**: the missing `restart:` policy on the `db` compose service, to be handled as a
  separate fix.
