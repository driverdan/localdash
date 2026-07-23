## 1. Registry: kind + City of Chattanooga source

- [x] 1.1 In `app/news/registry.py`, add the `chattgov` source to `SOURCES` ("City of Chattanooga",
  homepage `https://chattanooga.gov`, enabled) with a single feed: category `news`, `kind: "html"`,
  url `https://chattanooga.gov/stay-informed/latest-news`.
- [x] 1.2 Add a `feed_kind(url: str) -> str` helper that returns the feed's `kind` from `SOURCES`
  (default `"rss"`), mirroring the existing `uses_feed_tags(slug)` lookup.
- [x] 1.3 Confirm `sync_registry` needs no change (it upserts URL/category/position only; `kind`
  lives in the registry, not the DB) — no `news_feeds` schema change, no Alembic migration.

## 2. Fetcher: HTML scrape path

- [x] 2.1 Add `parse_html_listing(html: str, base_url: str) -> list[dict]` to `app/news/fetcher.py`:
  a pure function that parses `div.views-row` with `BeautifulSoup(html, "html.parser")` and returns
  per-row dicts `{"url", "title", "summary", "published", "image_url": None, "guid": url}`.
  - title/url from `.views-field-title h3 a` (`urljoin(base_url, href)`); skip a row missing either.
  - `published` from `.views-field-created time[datetime]` via `datetime.fromisoformat`, converted
    to UTC; fall back to `now(tz=utc)` when absent/unparseable.
  - `summary` from `.views-field-body .field-content` via `strip_html` + `truncate_sentences(…, 600)`.
- [x] 2.2 Add `_fetch_html(url: str) -> str` using `httpx.AsyncClient(follow_redirects=True)` with
  the registry `USER_AGENT`; raise for non-success status so the per-feed `try/except` records it.
- [x] 2.3 Branch `fetch_feed` on `feed_kind(feed.url)`: `html` → `_fetch_html` + `parse_html_listing`,
  then complete each row with `source_id`, `classify(title, summary, [], feed.category)`, and
  `fetched_at`, and pass to the existing `upsert_articles`; `rss` → the current `feedparser` body,
  unchanged. Return the same `(added, status)` tuple shape (report entry/changed counts, or a
  "no entries"-style status when the listing yields no rows).

## 3. Tests

- [x] 3.1 Save a representative `stay-informed/latest-news` HTML fixture (a few `.views-row`s,
  including one missing a title/link and one with an unparseable/missing date) under `tests/`.
- [x] 3.2 Add offline unit tests for `parse_html_listing` (no network, no DB), matching
  `test_news_fetcher.py` style: correct title/absolute-URL/summary extraction, UTC-normalized
  `published`, `guid == url`, `image_url is None`, malformed rows skipped, empty page → `[]`.
- [x] 3.3 Add a test for `feed_kind`: `chattgov`'s feed → `"html"`, an existing RSS feed → `"rss"`,
  an unknown URL → `"rss"` default.

## 4. Verify end-to-end

- [x] 4.1 Run the full test suite and `ruff`/formatting; ensure no regressions in the RSS path.
  (324 passed; the one failure, `test_news_db::test_stories_limit_returns_newest_slice`, is
  pre-existing — it fails identically with these changes stashed — and is unrelated to this change.)
- [x] 4.2 Rebuild and run via Docker (`docker compose up --build`), trigger `POST /api/v1/news/refresh`,
  and confirm `chattgov` articles appear in `GET /api/v1/news/stories` and that
  `GET /api/v1/news/sources` shows the `chattgov` feed with a success `last_status`.
  (Live refresh scraped 10 articles → `chattgov/news: ok (10 entries, 10 changed)`; published times
  UTC-normalized from the `-04:00` offset; categories content-classified; articles surface in
  `/stories` and the `/sources` footer shows the feed healthy.)
