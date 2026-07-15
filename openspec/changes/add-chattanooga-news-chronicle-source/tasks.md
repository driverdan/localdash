## 1. Registry

- [ ] 1.1 Add a Chattanooga News Chronicle entry to `SOURCES` in `app/news/registry.py`:
  slug `chattnewschronicle`, name `Chattanooga News Chronicle`, homepage
  `https://www.chattnewschronicle.com`, enabled `True`, with one feed
  `{category: "news", url: "https://www.chattnewschronicle.com/feed/"}`.

## 2. Verify

- [ ] 2.1 Rebuild and start the app (`docker compose up --build`) so `sync_registry()` runs.
- [ ] 2.2 Confirm the new source and feed are present via the news API/homepage (source
  `Chattanooga News Chronicle` listed; its articles appear under the `news` category once a
  refresh cycle completes) and that the feed's `last_status` is healthy.
- [ ] 2.3 Run the news test suite (`tests/test_news_*.py`) to confirm no regressions.
