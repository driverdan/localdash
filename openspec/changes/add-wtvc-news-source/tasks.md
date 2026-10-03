## 1. Registry

- [ ] 1.1 Add a WTVC entry to `SOURCES` in `app/news/registry.py`, after `chattgov`: slug
  `wtvc`, name `NewsChannel 9 (WTVC)`, homepage `https://newschannel9.com`, enabled `True`,
  `use_feed_tags: False`, and one feed
  `{category: "news", url: "https://newschannel9.com/news/local.rss"}` (default `rss` kind). Add a
  comment covering: Sinclair section-RSS convention (not advertised in HTML); `/sports.rss` and
  `/news.rss` deliberately skipped; every item is tagged `article`, hence tag-exempt; same
  newsroom as foxchattanooga.com, which must not be added as a second outlet; "Local" includes
  sister-station and wire items (known caveat).
- [ ] 1.2 Update the `SOURCES` header comment. It says "only the WordPress outlets — WDEF, the
  News Chronicle, and the library — emit per-item tags", which stops being true once WTVC is
  added. Note that WTVC also emits a tag but is tag-exempt.

## 2. Tests

- [ ] 2.1 In `tests/test_news_classify.py`, extend
  `test_tag_exempt_source_flag_is_read_from_the_registry` to assert `uses_feed_tags("wtvc") is
  False`.
- [ ] 2.2 Add an offline registry test asserting the `wtvc` source has exactly one feed,
  `https://newschannel9.com/news/local.rss`, with category `news`, and that
  `feed_kind(<that url>) == "rss"`.

## 3. Verify

- [ ] 3.1 Run the news test suite (`tests/test_news_*.py`) plus ruff, and confirm no regressions.
- [ ] 3.2 Rebuild and start the app (`docker compose up --build`) so `sync_registry()` runs.
- [ ] 3.3 Confirm via `GET /api/v1/news/sources` that the WTVC feed is present with a healthy
  `last_status` and a non-zero article count after the startup refresh. Confirm WTVC stories appear
  in `GET /api/v1/news/stories` with `image_url`s from the feed enclosures, and that at least one
  clusters with another outlet.
