## 1. Schema

- [ ] 1.1 Add nullable `image_url` (`Text`) column to `NewsArticle` in `app/news/models.py`
- [ ] 1.2 Add Alembic revision `0007_news_image_url.py` (raw SQL: `ALTER TABLE news_articles ADD COLUMN image_url text`, with a matching downgrade)

## 2. Fetcher

- [ ] 2.1 Add an image-extraction helper in `app/news/fetcher.py`: return the first image `enclosure` URL, else the first `<img src>` in the item's content/summary HTML, else `None`
- [ ] 2.2 Include `image_url` in the row dict built in `fetch_feed`
- [ ] 2.3 Add `image_url` to the `pg_insert` column set (leave the on-conflict update untouched — conflicts still only upgrade category)

## 3. Story read model + API

- [ ] 3.1 Select `NewsArticle.image_url` in `get_stories` and pass it through in each row dict
- [ ] 3.2 In `build_stories`, set the story's `image_url` to the first member (published-ascending) whose `image_url` is non-null, else `None`
- [ ] 3.3 Ensure `app/api/news.py` includes `image_url` in the story response (update the response model / serializer if it enumerates fields)

## 4. Frontend

- [ ] 4.1 Add `image_url: string | null` to `Story` in `frontend/src/features/news/types.ts`
- [ ] 4.2 Render the image in `StoryCard.svelte` only when `story.image_url` is truthy (no placeholder when null)
- [ ] 4.3 Add story-image styling to `frontend/src/styles/news.css` (constrain max-width/aspect, `object-fit`, graceful on load failure); no scoped `<style>` block

## 5. Tests & verification

- [ ] 5.1 Extend `tests/test_news_db.py` (or fetcher-level test) so an item with an image enclosure and one with an inline `<img>` store the expected `image_url`, and one with neither stores `None`
- [ ] 5.2 Extend `tests/test_news_clustering.py` `build_stories` coverage: a story borrows the earliest member's image; a cluster with no images yields `image_url: None`
- [ ] 5.3 Rebuild Docker (`docker compose up --build`), run a refresh, and confirm story cards show images for image-bearing outlets (e.g. Local 3) and text-only cards render unchanged
