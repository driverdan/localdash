## 1. Formatting helper

- [x] 1.1 Add `fmtEventDate(startsAt: string, endsAt: string | null): string` to
  `frontend/src/lib/format.ts`: local-calendar-day diff → `Today` / `Tomorrow` / weekday name
  (2–6 days) / formatted date (7+ days, year only when it differs from the current year), then
  ` · ` and seconds-free start time, with ` – ` and the end time when `endsAt` is set

## 2. Event card

- [x] 2.1 Replace the `when` derivation in
  `frontend/src/features/events/components/EventCard.svelte` with a single
  `fmtEventDate(item.starts_at, item.ends_at)` call and drop the now-unused `fmt` import

## 3. Verify

- [x] 3.1 Run `npm run check` in `frontend/` (svelte-check passes)
- [x] 3.2 Rebuild with `sg docker -c 'docker compose up --build -d'` and visually confirm cards
  on `/events` and the home page show `Today` / `Tomorrow` / weekday / far-date forms with
  seconds-free times
