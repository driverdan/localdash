## 1. Data layer

- [ ] 1.1 In `frontend/src/features/home/api.ts`, add types for the outage digest (per-service `{count, customers}` summary) and a `loadOutages()` loader that fetches `/api/v1/timeseries/entities?source=epb` and reduces active features to the per-service summary (missing/non-positive `customer_quantity` counts as zero).
- [ ] 1.2 In `frontend/src/features/home/state.svelte.ts`, add outage digest state: the summary plus `outagesLoaded`/`outagesError` flags matching the sibling widgets.

## 2. Widget component

- [ ] 2.1 Create `frontend/src/features/home/components/OutageDigest.svelte`: heading "Outages" with a client-side "View all →" link to `/map`; one row per service with active outages ("N power outage(s)" / "N fiber outage(s)", "· X customers" only when the summed quantity is positive); "No current outages" zero state; error notice on failed load. Always rendered — no visibility logic.
- [ ] 2.2 Mount it in `HomePage.svelte`'s `widget-column` between `WeatherStrip` and the events article, and add `loadOutages()` to the on-mount fetches.
- [ ] 2.3 Style the widget in `frontend/src/styles/home.css` per the global styling contract (no scoped styles), consistent with the weather strip's compact rows.

## 3. Live updates

- [ ] 3.1 In `frontend/src/features/home/live.ts`, add a permanent `subscribe("timeseries", ...)` that calls `loadOutages()` only when `msg.source === "epb"`, and add `loadOutages` to the `onReconnect` refetch list.

## 4. Specs and verification

- [ ] 4.1 Run `svelte-check` and prettier; rebuild via `sg docker -c 'docker compose up --build'`.
- [ ] 4.2 Verify in the running app: widget renders beneath weather (zero state or live counts), "View all →" navigates client-side to `/map`, and a manual `POST /api/v1/timeseries/sources/epb/refresh` (or next poll) live-updates the digest without a reload.
