## 1. Backend filter

- [ ] 1.1 In `app/api/events.py`, change the `upcoming` predicate from
      `Event.starts_at >= now` to `coalesce(Event.ends_at, Event.starts_at) >= now`, and update
      the query-parameter description to "Only events that have not ended".

## 2. Tests

- [ ] 2.1 In `tests/test_api_events.py`, extend the default-listing test (or add a sibling) to
      cover: an in-progress event (started, `ends_at` in the future) is included; an ended event
      is excluded; a started event with `ends_at=None` is excluded.

## 3. Verify

- [ ] 3.1 Run the backend test suite.
- [ ] 3.2 Rebuild with `docker compose up --build` (via `sg docker`) and confirm
      `GET /api/v1/events/items` now returns currently in-progress events and both the Events
      page and homepage digest show them.
