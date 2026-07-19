## 1. Shared local-day helper

- [ ] 1.1 In `frontend/src/lib/format.ts`, extract the local-midnight day-diff `fmtEventDate`
      already computes into a small reusable helper (e.g. `isLocalToday(iso: string): boolean`, or
      a shared day-diff the helper wraps), and refactor `fmtEventDate` to use it so the "Today"
      label and the digest filter share one definition.

## 2. Scope the digest to today

- [ ] 2.1 In `frontend/src/features/home/api.ts`, `loadEvents()`: after fetching, filter the
      returned items to only those whose `starts_at` is the current local day (via the helper from
      1.1) before assigning `home.events`. Leave the request URL (`?limit=10&max_miles=35`)
      unchanged. Update the `loadEvents()` doc comment to describe the same-day scope.

## 3. Rename the widget

- [ ] 3.1 In `frontend/src/features/home/components/HomePage.svelte`, change the widget heading
      from "Current events" to "Today's events".
- [ ] 3.2 In the same file, change the empty-state notice from "No current events." to
      "No events today."

## 4. Verify

- [ ] 4.1 Rebuild the frontend (`docker compose up --build`) and confirm the home page shows a
      "Today's events" widget listing only events that start today, and the empty state when none
      do.
- [ ] 4.2 Run the frontend checks (svelte-check / lint) to confirm no type or lint regressions.
