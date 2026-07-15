## Context

News articles are stored with a `category` that is inherited from the RSS feed (outlet section) they
arrived in — see `app/news/registry.py` (feeds map to a category) and `app/news/fetcher.py` (the feed
category is written onto the article). Story-level category is a majority vote over member articles in
`app/news/stories.py`. Two consequences motivate this change:

- Single-feed outlets have no internal categorization: every article from The Pulse is `life`, every
  article from the News Chronicle is `news`.
- The category tracks *which section fetched a story*, not *what the story is about*.

Constraints and existing patterns:
- The repo already has a deterministic, keyword-based per-record classifier for the sibling **events**
  feature (`app/events/tagging.py`: a topic→keywords map, case-insensitive substring match over
  title+description). This change deliberately mirrors it.
- Investigation of the live feeds (2026-07) found the two WordPress outlets — **WDEF** and the **News
  Chronicle** — *do* emit per-item `<category>` tags (feedparser exposes them as `entry.tags`),
  contradicting the current registry/spec claim that no outlet does. Their vocabulary is a noisy
  WordPress category+tag bag (topics mixed with geography, `Featured`/`Top Stories` flags, campaign
  names, and free-text one-offs), so only a curated subset is usable. The other four outlets emit no
  per-item tags.
- Normalized categories are fixed: `news`, `sports`, `business`, `politics`, `opinion`, `life`
  (`registry.CATEGORIES`). `news` is the generic/catch-all bucket.

## Goals / Non-Goals

**Goals:**
- Derive each article's category from its own content, resolved deterministically and offline.
- Reuse the events `tagging.py` shape so the two classifiers read as one system.
- Harvest the WordPress feed `<category>` tags as a high-value prior where they map cleanly
  (especially `Commentary`→`opinion`, which keywords cannot reliably detect — opinion is a format,
  not a topic).
- Preserve the single-category-per-story model and the existing tabs / grouped "All" UI.
- Correct the false "no per-item categories" claims in the registry comment and `news` spec.

**Non-Goals:**
- Multi-tag stories (event-style tag sets). Considered and declined for this change; keep 1:1.
- Any LLM / external classification service or new runtime dependency.
- Changing the clustering algorithm or the `/api/v1/news/stories` response shape.
- Fetching article pages for richer text — classification uses feed title+summary only.
- Adding new categories (e.g. a `local` bucket for the geographic WordPress tags).

## Decisions

### Three-tier resolution: mapped feed tag → keyword match → feed-section fallback
Category for an article is the first of:
1. A **mapped feed `<category>` tag** (curated tag→category map; unmapped tags ignored).
2. A **keyword match** on title + HTML-stripped summary (topic→keyword map, events-style).
3. The **feed's registered section category** (today's behavior), so nothing is left uncategorized.

*Why this order:* the WordPress tags, when they map, are editorial ground truth stronger than a
keyword guess (a human tagged the post `Commentary`). Keywords generalize to the four outlets with no
tags. The feed section is a safe floor that preserves current behavior when neither fires — so this is
strictly additive precision, never worse than today.

*Alternatives considered:* keyword-only (simpler, but throws away the one signal that reliably
catches opinion pieces); feed-tags-only (covers just 2/6 outlets); LLM (best accuracy on terse
headlines but adds a dependency, key management, cost, and nondeterministic tests — rejected per the
repo's deterministic bent).

### A dedicated classifier module mirroring events/tagging.py
Add an `app/news/` module (e.g. `classify.py`) holding two code-defined maps — `TAG_CATEGORY_MAP`
(feed tag string → normalized category) and `TOPIC_KEYWORDS` (normalized category → keyword list) —
plus a `classify(title, summary, feed_tags, feed_category)` function returning one normalized
category. Code is the source of truth, matching `registry.py` and `events/tagging.py`. This keeps the
maps reviewable/tunable in one place and independently unit-testable (pure function, offline).

*Note:* news categories double as the classifier's output vocabulary, unlike events where topics are
their own set. The keyword map is therefore keyed by the six normalized categories, not a separate
topic space.

### Capture feed `<category>` tags in the fetcher
`fetcher.py` currently reads feedparser entries but discards `entry.tags`. It will collect
`[t.term for t in entry.get("tags", [])]` and pass them to `classify(...)`. No new stored column is
required — tags are consumed at classify time; only the resolved `category` is persisted. (If a future
change wants the raw tags for multi-tag, that's a separate schema addition, explicitly out of scope.)

### Replace the dedup category-upgrade rule with recompute-on-fetch
Today the upsert "only upgrades a generic `news` category to a specific section category (never the
reverse)" — a rule that exists purely because category came from feeds and a later specific feed was
better evidence than an earlier general one. With content classification, the category is a stable
function of the article's own content, so the upsert SHALL recompute and overwrite `category` on every
fetch. This is simpler and removes a special case; a re-fetch simply reflects the current maps.

### Redefine the sources footer per-category count as a per-source total
`get_stories`/`get_sources` in `stories.py`: the sources query counts articles via
`article.category == feed.category`, which meant "articles this feed produced." Once category
decouples from feed section that join is misleading. Reduce it to a per-source total article count.
The feed-health fields (last_fetch/last_status/etc.) are untouched, so the footer's health role is
preserved; only the count's definition changes.

## Risks / Trade-offs

- **Keyword classifier is crude on terse headlines** → title+summary substring matching will
  mis-file or under-file some stories. Mitigation: the feed-section fallback guarantees no regression
  below today's behavior; the maps are code-defined and tunable; unit tests pin known cases.
- **WordPress tag vocabulary is noisy and can drift** → curating `TAG_CATEGORY_MAP` risks mapping a
  tag that later changes meaning. Mitigation: map only a small, high-confidence subset (`Commentary`,
  `Local News`, `Top Stories`, `News`, `Local`); ignore everything else; unmapped tags fall through
  to keyword/fallback.
- **Opinion detection still leans on tags** → the four non-WordPress outlets have no reliable opinion
  signal from content keywords. Accepted: their opinion pieces come via `.../Opinion/feed` and keep
  the feed-section fallback of `opinion`, so nothing regresses.
- **Existing rows recategorize on next fetch** → category values shift after deploy. Acceptable: no
  schema change, self-heals within one refresh cycle (default 15 min), and the story API shape is
  unchanged so the frontend needs no coordination.
- **Cluster majority vote interaction** → per-article categories within one story now tend to agree,
  making the vote cleaner; no contract change, but tests over `build_stories` should confirm the vote
  still resolves ties (specific beats `news`) as before.

## Migration Plan

1. Land the classifier module + maps with unit tests (pure, offline).
2. Wire capture of `entry.tags` and `classify(...)` into `fetcher.py`; replace the upsert
   category-upgrade branch with recompute-on-fetch.
3. Update `stories.get_sources` count definition.
4. Correct the registry comment and sync the `news` spec.
5. Deploy; the next scheduled refresh recomputes all live rows. Rollback is code-only (revert);
   the next refresh restores feed-derived categories — no data migration either direction.

## Open Questions

- Exact seed contents of `TOPIC_KEYWORDS` per category and the curated `TAG_CATEGORY_MAP` — to be
  finalized during implementation against a larger live sample; the design fixes the mechanism, not
  the every last keyword.
