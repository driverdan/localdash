## 1. Classifier module

- [ ] 1.1 Add `app/news/classify.py` with two code-defined maps: `TAG_CATEGORY_MAP` (feed
  `<category>` tag string → normalized category, e.g. `Commentary`→`opinion`, `Local News`/`Top
  Stories`/`News`/`Local`→`news`) and `TOPIC_KEYWORDS` (normalized category → keyword list), seeded
  from the six categories in `registry.CATEGORIES` and modeled on `app/events/tagging.py`.
- [ ] 1.2 Implement `classify(title, summary, feed_tags, feed_category) -> str` applying the ordered
  rules: mapped feed tag → keyword match on title+HTML-stripped summary → feed-section fallback,
  returning one normalized category. Ignore unmapped tags.
- [ ] 1.3 Add `tests/test_news_classify.py` covering: tag maps to opinion (Commentary), keyword match
  when no mapped tag, unmapped tags + no keyword falls back to feed category, and a single-feed-outlet
  article classified away from its feed section.

## 2. Wire classification into the fetch path

- [ ] 2.1 In `app/news/fetcher.py`, collect each entry's feed tags (`[t.term for t in
  entry.get("tags", [])]`) alongside the fields already extracted.
- [ ] 2.2 Call `classify(...)` when building the article and store the resolved category; replace the
  dedup upsert's "only upgrade generic `news`→specific section" branch with recompute-and-overwrite
  `category` on every fetch (keep GUID dedup, no duplicate rows).
- [ ] 2.3 Update `tests/test_news_fetcher.py` / `tests/test_news_db.py` for the new categorization and
  the recompute-on-fetch upsert behavior (a re-fetch reflects current classification, not a one-way
  upgrade).

## 3. Sources API count

- [ ] 3.1 In `app/news/stories.py` `get_sources`, redefine the per-source article count as a
  per-source total (drop the `article.category == feed.category` correlation); leave feed-health
  fields unchanged.
- [ ] 3.2 Update the corresponding sources API test to assert the per-source total count.

## 4. Documentation & spec sync

- [ ] 4.1 Correct the false "None of the sites put `<category>` tags" comment in
  `app/news/registry.py` (WDEF and the News Chronicle do; tags are used as priors).
- [ ] 4.2 Run `/opsx:sync` (or `openspec sync`) to fold the delta into `openspec/specs/news/spec.md`
  and reconcile the earlier categorization scenarios.

## 5. Verify

- [ ] 5.1 Rebuild via `docker compose up --build`, trigger `POST /api/v1/news/refresh`, and confirm
  stories from single-feed outlets (The Pulse, News Chronicle) appear under content-appropriate tabs
  rather than all under one category, and that a Chronicle `Commentary` item lands in Opinion.
