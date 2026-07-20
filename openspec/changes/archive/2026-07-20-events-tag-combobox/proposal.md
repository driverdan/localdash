## Why

The Events page renders every known topic tag as an always-visible row of toggle chips. As the
number of configured event sources (and thus tags) grows, that row becomes long and noisy, and it
gives no fast way to reach a specific tag. A type-to-filter combobox scales better and lets users
find and apply tags directly.

## What Changes

- **BREAKING (UI)**: Replace the topic chip row on the Events page with a tag **combobox** — a text
  input that filters tag suggestions as the user types, with the selected tags shown as removable
  pills beside the input.
- When the input is empty and focused, the dropdown shows the **full** known-tag list; typing
  refines the suggestions (case-insensitive substring match), excluding tags already selected.
- Selecting a suggestion adds it as a pill and refetches `GET /api/v1/events/items`; removing a pill
  clears that topic and refetches. Filtering stays server-side, exactly as today.
- Only tags from the known list (`GET /api/v1/events/tags`) can be selected — free-typed text that
  matches no known tag cannot be committed, consistent with today's pruning of unknown saved topics.
- Provide keyboard navigation and accessible combobox semantics (arrow keys, Enter to select, Escape
  to close, Backspace to remove the last pill; ARIA combobox/listbox roles and active-descendant).
- Reuse the existing state (`events.tags` candidates, `events.topics` active set, `toggleTopic`,
  `localdash.events` persistence) and the existing API layer unchanged — this is a presentation
  change plus a small selectors helper if needed.
- Custom dropdown (not a native `<datalist>`) so selected pills can be shown and the dropdown styled
  through the global events stylesheet.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `frontend-events`: The "Topic, distance, and search filtering" requirement changes — topic
  selection is a type-to-filter combobox with removable pills instead of a multi-select chip row.
  The "Styles via the global styling contract" requirement is updated to reference the combobox and
  pill markup (and its dropdown) rather than "topic chips".

## Impact

- `frontend/src/features/events/components/EventsPage.svelte` — replace the chip row with the
  combobox/pills UI, wiring, and keyboard handling.
- Possibly a small new presentation component (e.g. `TagCombobox.svelte`) and/or a selectors helper
  on `events.svelte.ts` for the filtered-suggestion list.
- `frontend/src/styles/events.css` — add combobox, dropdown, and pill styles; retire chip styles.
- No backend, API-contract, or persistence-format changes: `/api/v1/events/tags`,
  `/api/v1/events/items`, and the `localdash.events` prefs shape are untouched.
