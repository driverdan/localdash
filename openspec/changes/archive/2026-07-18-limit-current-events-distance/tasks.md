## 1. Implementation

- [x] 1.1 In `frontend/src/features/home/api.ts`, update `loadEvents` to fetch
  `/api/v1/events/items?limit=10&max_miles=35`.

## 2. Verification

- [x] 2.1 Rebuild the frontend and bring up the stack (`docker compose up --build`).
- [x] 2.2 Load `/` and confirm the "Current events" digest shows only events within 35 miles of
  the configured center (events farther away no longer appear).
