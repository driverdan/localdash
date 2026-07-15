## Why

A story's category today is inherited from the RSS feed (outlet section) it arrived in, so
categorization mirrors *which section fetched a story* rather than *what the story is about*. Whole
single-feed outlets collapse into one bucket — every article from The Pulse is `life`, every article
from the News Chronicle is `news` — and a hard-news story from an arts weekly (or a sports recap from
a general feed) lands in the wrong tab. Categorizing each story by its own content fixes this.

## What Changes

- Each article's category is derived **per article from its own content** instead of being inherited
  wholesale from its feed's section. Category is resolved by a three-tier rule, first match wins:
  1. **Mapped feed `<category>` tag** — the two WordPress outlets (WDEF, News Chronicle) emit
     per-item `<category>` tags; where one maps cleanly into our vocabulary (e.g. `Commentary` →
     `opinion`, `Local News`/`Top Stories` → `news`) it is used as a prior.
  2. **Keyword classification** — a topic→keyword map matched against the article's title + summary,
     mirroring the existing `app/events/tagging.py` pattern.
  3. **Feed-section category** — today's behavior, kept as the last-resort fallback so nothing lands
     without a category.
- The story stays **single-category** (one category per story); tabs and the grouped "All" view are
  unchanged. Only how the underlying category is chosen changes.
- The fetcher captures feed `<category>` tags (via feedparser `entry.tags`) so tier 1 has data.
- The dedup upsert's "only upgrade generic `news` → specific section" rule is **replaced**: because
  category is now content-derived and stable per article, re-fetches recompute and overwrite the
  category rather than one-way upgrading it.
- Correct the record: the registry comment and `news` spec currently assert *no* outlet emits
  per-item categories — verified false (WDEF and the News Chronicle both do).

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `news`: article categorization changes from feed-section inheritance to per-article content
  classification (feed-tag prior → keyword match → feed-section fallback); the dedup category-upgrade
  rule and the false "no per-item categories" claims are revised accordingly.

## Impact

- **Code**: `app/news/` — new classifier module (topic→keyword map + feed-tag mapping), wired into
  `fetcher.py` (capture `<category>` tags; classify on store) and the dedup upsert in the fetch path;
  registry/spec comment corrections. `app/news/stories.py` cluster majority-vote is unaffected by
  contract but benefits from cleaner per-article categories.
- **API**: `GET /api/v1/news/stories` and the category tabs it feeds are unchanged in shape; only the
  category values a given story receives change. `GET /api/v1/news/sources` per-category counts (which
  join `article.category == feed.category`) no longer mean "articles this feed produced" and need
  redefining or reduction to per-source totals.
- **Dependencies**: none new — deterministic keyword/tag matching, no LLM or external service.
- **Data**: existing `news_articles.category` values are recomputed on the next fetch cycle; no schema
  change required.
