## 1. Classifier module

- [x] 1.1 Add `app/news/classify.py` with two code-defined maps: `TAG_CATEGORY_MAP` (feed
  `<category>` tag string → normalized category, e.g. `Commentary`→`opinion`, `Local News`/`Top
  Stories`/`News`/`Local`→`news`) and `TOPIC_KEYWORDS` (normalized category → keyword list), seeded
  from the six categories in `registry.CATEGORIES` and modeled on `app/events/tagging.py`.
- [x] 1.2 Implement `classify(title, summary, feed_tags, feed_category) -> str` applying the ordered
  rules: mapped feed tag → keyword match on title+HTML-stripped summary → feed-section fallback,
  returning one normalized category. Ignore unmapped tags. (A specific mapped tag beats a generic
  `news` tag on the same item.)
- [x] 1.3 Add `tests/test_news_classify.py` covering: tag maps to opinion (Commentary), keyword match
  when no mapped tag, unmapped tags + no keyword falls back to feed category, and a single-feed-outlet
  article classified away from its feed section.

## 2. Wire classification into the fetch path

- [x] 2.1 In `app/news/fetcher.py`, collect each entry's feed tags (`_entry_tags`, from
  `entry.tags` terms) alongside the fields already extracted.
- [x] 2.2 Call `classify(...)` when building the article and store the resolved category; replace the
  dedup upsert's "only upgrade generic `news`→specific section" branch with recompute-and-overwrite
  `category` on every fetch (keep GUID dedup, no duplicate rows).
- [x] 2.3 Update `tests/test_news_db.py` for the new categorization and the recompute-on-fetch upsert
  behavior (a re-fetch reflects current classification, not a one-way upgrade).

## 3. Sources API count

- [x] 3.1 In `app/news/stories.py` `get_sources`, redefine the per-source article count as a
  per-source total (drop the `article.category == feed.category` correlation); leave feed-health
  fields unchanged.
- [x] 3.2 Update the corresponding sources API test to assert the per-source total count.

## 4. Documentation

- [x] 4.1 Correct the false "no `<category>` tags" comments in `app/news/registry.py` and
  `app/news/models.py` (WDEF and the News Chronicle do; tags are used as priors).

> Note: syncing the delta into `openspec/specs/news/spec.md` is the archive phase (PR #3, via
> `/opsx:sync`), kept out of this code-only implementation PR.

## 5. Verify

- [x] 5.1 Exercised the live code path (`_entry_tags` + `classify`) against the real Pulse, News
  Chronicle, and WDEF feeds: the Chronicle's `Commentary`-tagged column classifies as `opinion`, and
  single-feed outlets no longer collapse wholesale into their feed section. Tuned out a keyword
  false positive (`campaign` matching a marketing campaign) found during verification. Full suite
  (196 tests, incl. DB-backed news tests) and ruff pass.
