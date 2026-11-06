## 1. Labeled fixture

- [ ] 1.1 Export a contiguous real window of 10–14 days of articles from the DB (id, outlet slug,
  published ISO-8601, title, feed summary) into a scratch file. The window must include
  Oct 24 – Nov 2, 2026, which holds the explore-session hard cases.
- [ ] 1.2 Seed candidate story groups from the union of the current algorithm's clusters and the
  prototype's clusters (design D3/D4 initial thresholds) over that window.
- [ ] 1.3 Hand-verify every candidate group: split groups that mix events, merge missed same-event
  articles, and give every other article a singleton label. Confirm the design D6 hard cases are
  present and labeled correctly (Lee Hwy / Chickamauga Dam / Nashville chain, DECISION 2026
  series, Arrest Report dailies, Red Bank grab-bag, Mocs vs Gators, Baylor vs Asbury; true
  positives airport, Aquarium, Hwy 27, Blackford St, Red Wolves).
- [ ] 1.4 Write `tests/fixtures/news_clustering.json` (articles with a `story` label each). Keep
  only title and feed summary; no article bodies.
- [ ] 1.5 Add a pairwise precision/recall helper in the test module that scores a clustering
  (`{article_id: cluster_id}`) against the gold `story` labels. Record the **current** algorithm's
  precision and recall on the fixture for the PR description.

## 2. Tokenizer and weighting

- [ ] 2.1 Change `textutil.title_tokens` to keep numeric tokens of any length (words still need
  more than 2 characters and must not be stopwords). Update `test_strip_html_and_tokens` to match.
- [ ] 2.2 In `app/news/clustering.py`, add a pure document-frequency builder over a corpus of
  `(title, summary)` items. It returns two IDF maps, title tokens and title+summary tokens, using
  `ln((N+1)/(df+1))`. Unknown tokens get the maximum IDF.
- [ ] 2.3 Add pure weighted-Jaccard and weighted-containment helpers over token sets plus an IDF
  map.

## 3. Match predicate

- [ ] 3.1 Implement the title score (design D3.1): weighted Jaccard ≥ `MATCH_JACCARD`, or weighted
  containment ≥ `MATCH_CONTAINMENT` with weighted Jaccard ≥ `CONTAINMENT_JACCARD_FLOOR` and at
  least 2 shared tokens.
- [ ] 3.2 Implement the number veto: both titles have numeric tokens (excluding four-digit
  `19xx`/`20xx` years) and the sets are disjoint.
- [ ] 3.3 Implement the summary veto: both summaries are at least 40 chars, and the title+summary
  weighted Jaccard is below `SUMMARY_VETO`.
- [ ] 3.4 Implement the recurring-column exception: same `source_id`, identical title after
  ignoring case, punctuation, whitespace and a trailing plural "s", published more than 12h
  apart.
- [ ] 3.5 Remove the `SequenceMatcher` fallback, the cross-outlet distinctive-token rule, the
  same-outlet guard, and their constants.

## 4. Assignment and DB wrapper

- [ ] 4.1 Rewrite `assign_clusters(articles, corpus)` as chronological majority-match assignment
  (design D4): process in `(published, id)` order; candidate stories are those whose anchor is
  within `STORY_WINDOW_HOURS = 36`; join when `2 × hits ≥ members`, choosing the highest match
  fraction, then the earlier anchor, then the smaller id. Return `{article_id: smallest member id}`.
- [ ] 4.2 Update `recluster(session)`: load window articles (id, source_id, published, title,
  summary) plus the `IDF_LOOKBACK_DAYS = 30` corpus (title, summary). Run `assign_clusters` in
  `asyncio.to_thread` and write `cluster_id`s as today. Keep the signature and return value.
- [ ] 4.3 Rewrite the module docstring to describe the new algorithm, so it no longer claims to be
  the ChattNews port.

## 5. Tests and tuning

- [ ] 5.1 Rewrite `tests/test_news_clustering.py` clustering tests with one focused test per spec
  scenario: two-outlet same event, DECISION-style series separate (number veto), generic-word
  pair separate (IDF), weak link doesn't chain (majority match), follow-up after 36h is a new
  story, recurring same-title column separate, same-outlet near-duplicate within 12h merges,
  summary veto, smallest-id convention, determinism (shuffled input gives identical output).
- [ ] 5.2 Add the fixture test: `assign_clusters(fixture, fixture)` must reach precision ≥ 0.85
  and recall ≥ 0.45 against gold labels.
- [ ] 5.3 Tune `MATCH_JACCARD`, `MATCH_CONTAINMENT`, `CONTAINMENT_JACCARD_FLOOR` and
  `SUMMARY_VETO` against the fixture, favoring precision, and record the final values as module
  constants. If the targets can't be met, stop and revise the design (do not lower the targets
  in the test).
- [ ] 5.4 Leave the existing `build_stories` tests untouched, and confirm they still pass.

## 6. Verify

- [ ] 6.1 Run the full test suite, ruff, and the repo's pre-commit checks; confirm no regressions.
- [ ] 6.2 Rebuild and start the stack (`docker compose up --build`) and trigger
  `POST /api/v1/news/refresh`.
- [ ] 6.3 Check `GET /api/v1/news/stories?hours=168`: no story mixes unrelated events, the largest
  story is a single event, and DECISION 2026 / Arrest Report posts are separate stories. Note the
  before/after story counts in the PR description.
