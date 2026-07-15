## 1. Registry

- [x] 1.1 Add a The Pulse entry to `SOURCES` in `app/news/registry.py`:
  slug `chattanoogapulse`, name `The Pulse`, homepage
  `https://www.chattanoogapulse.com`, enabled `True`, with one feed
  `{category: "life", url: "https://www.chattanoogapulse.com/api/rss/content.rss"}`.

## 2. Verify

- [x] 2.1 Rebuild and start the app (`docker compose up --build`) so `sync_registry()` runs.
- [x] 2.2 Confirm the new source and feed are present via the news API/homepage (source
  `The Pulse` listed; its articles appear under the `life` category once a refresh cycle
  completes) and that the feed's `last_status` is healthy.
- [x] 2.3 Run the news test suite (`tests/test_news_*.py`) to confirm no regressions.
