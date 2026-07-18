## 1. Rename the widget label

- [x] 1.1 In `frontend/src/features/home/components/HomePage.svelte`, change the events widget
  heading `<h2>` from "Upcoming events" to "Current events".
- [x] 1.2 In the same file, update the empty-state notice copy from "No upcoming events." to "No
  current events." so it stays consistent with the new label.

## 2. Increase the event count to 10

- [x] 2.1 In `frontend/src/features/home/api.ts`, change `loadEvents()`'s request from
  `/api/v1/events/items?limit=5` to `/api/v1/events/items?limit=10`.
- [x] 2.2 Update the `loadEvents()` doc comment so it describes fetching the next 10 events (not 5).

## 3. Verify

- [x] 3.1 Run `npm run check` in `frontend/` and confirm 0 errors.
- [x] 3.2 Run `npm run build` in `frontend/`, then load `/` and confirm the widget reads "Current
  events" and renders up to 10 rows.
