## 1. Digest component

- [ ] 1.1 Create `frontend/src/features/home/components/EventDigest.svelte`: takes an
  `EventItem` prop; renders the title linked to `item.links[0]?.source_url`
  (`target="_blank" rel="noopener"`, plain text when absent) and a second line with
  `fmtEventDate(item.starts_at, item.ends_at)` plus `· <n> mi` when `distance_miles` is
  non-null — nothing else
- [ ] 1.2 In `HomePage.svelte`, render `EventDigest` instead of `EventCard` in the events
  widget, drop the `id="events"` on the widget body, and remove the now-unused
  `EventCard` import from `features/events`

## 2. Styling

- [ ] 2.1 Add `.event-digest` row styles to `frontend/src/styles/home.css` (theme variables,
  wrapping titles, muted date/distance line) and remove the `.widget #events`
  neutralization and `.widget #events .event-card .image img` trim rules (keep the
  `#news` halves)
- [ ] 2.2 Update the `home.css` header comment: card reuse applies where the digest is the
  full card (news); home owns compact renderings otherwise (weather, events)

## 3. Events public surface cleanup

- [ ] 3.1 Verify nothing imports `EventCard` from `features/events/index.ts` anymore; drop
  the export and its home-digest comment (events' own page imports the component
  directly)

## 4. Verification

- [ ] 4.1 Run the frontend checks (svelte-check / lint / format) and fix any fallout
- [ ] 4.2 Rebuild and run via `sg docker -c 'docker compose up --build'` and verify on `/`:
  five abbreviated rows (linked title + date/time + distance only), title opens the
  source in a new tab, events page still renders full cards unchanged
