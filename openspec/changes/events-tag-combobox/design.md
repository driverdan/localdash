## Context

The Events page (`EventsPage.svelte`) filters topics via a chip row: `events.tags` (all known tags)
renders as toggle buttons, `events.topics` (active set) highlights the selected ones, and
`toggleTopic` flips membership then refetches. Filtering is entirely server-side — every filter
change re-requests `/api/v1/events/items` — so `events.items` always equals the current match. Topics
and max distance persist to `localdash.events`; on load, saved topics are intersected with the live
tag list (`loadTags`), dropping any that no longer exist.

The codebase has **no** existing autocomplete/combobox/typeahead pattern to copy. Styling follows the
`frontend-styling` contract: components carry no scoped `<style>`; all visuals live in
`frontend/src/styles/events.css` targeting semantic hooks.

## Goals / Non-Goals

**Goals:**
- Replace the always-visible chip row with a type-to-filter combobox whose selected tags show as
  removable pills.
- Empty+focused shows the full known-tag list; typing refines by case-insensitive substring,
  excluding already-selected tags.
- Full keyboard operation and accessible combobox/listbox semantics.
- Reuse `events.tags`, `events.topics`, `toggleTopic`, the API layer, and the persistence format
  unchanged.

**Non-Goals:**
- No backend, `/api/v1/events/*` contract, or `localdash.events` schema changes.
- No client-side filtering of items (server-side stays authoritative).
- No fuzzy/ranked matching, tag creation, tag counts, or grouping — plain substring match only.

## Decisions

### Custom combobox, not native `<datalist>`
A `<datalist>` gives free browser autocomplete but cannot render the selected-pills UI, cannot
exclude already-selected options, and styles inconsistently across browsers. The proposal requires
pills and a styled dropdown, so a custom component is necessary. Cost is the usual combobox
plumbing: keyboard nav, active-descendant, and click/focus-outside close.

### A dedicated `TagCombobox.svelte` presentation component
Isolate the input + dropdown + pills and their keyboard/ARIA handling in one component under
`features/events/components/`, keeping `EventsPage.svelte` a thin composition. The component takes the
candidate list, the selected list, and `onToggle`/`onSelect`/`onRemove` callbacks; it owns only local
UI state (query text, open flag, active index) and holds no feature state. Alternative — inlining
everything in `EventsPage.svelte` — was rejected as it would bloat an already filter-heavy file and
mix combobox mechanics with page composition.

### Derive suggestions in the component from props
The filtered suggestion list is `events.tags` minus `events.topics`, then substring-filtered by the
query — a pure function of inputs, computed with `$derived` inside the component. No new persisted or
store state is introduced. A `selectors` helper on the store was considered but is unnecessary since
the derivation is trivial and local to the view.

### Selection reuses `toggleTopic` + `loadItems`
Adding a suggestion or removing a pill calls the existing `toggleTopic(name)` then `loadItems()`,
exactly as the chip handler does today — same server-side refetch, same persistence effect. No new
mutation paths, so the "known-list-only" and prune-on-load guarantees hold automatically (a topic can
only be added by picking a candidate drawn from `events.tags`).

### Keyboard & ARIA model
Input is `role="combobox"` with `aria-expanded`, `aria-controls` → the listbox, and
`aria-activedescendant` → the active option id. The dropdown is `role="listbox"`; each suggestion is
`role="option"`. ArrowUp/Down move the active index (clamped), Enter commits the active suggestion,
Escape closes, and Backspace on an empty query removes the last pill. Pills expose an accessible
remove control (labeled button).

## Risks / Trade-offs

- **Discoverability of the full tag set is reduced** vs. the always-visible chip row → Mitigated by
  showing the entire known-tag list on empty focus, so one click still reveals everything.
- **Accessibility regressions** are easy to get wrong in a hand-rolled combobox → Mitigated by
  following the standard ARIA combobox/listbox pattern and covering keyboard paths in the specs'
  scenarios; verify with keyboard-only interaction.
- **Focus/close edge cases** (blur while clicking a suggestion, Escape, outside click) → Handle
  selection on pointerdown/mousedown before blur closes the list, and gate close on focus leaving the
  whole component.
- **Empty-state copy** in `EventsPage` references filters; keep the existing "no matches / sources
  may not be configured" logic keyed off `events.topics`/`search`/`maxMiles`, unchanged.

## Migration Plan

Pure frontend swap. Replace the chip block in `EventsPage.svelte` with `<TagCombobox>`, add combobox/
dropdown/pill rules to `events.css`, and remove the now-unused chip styles. Persistence format and
API are untouched, so no data migration and no rollback beyond reverting the frontend commit. Rebuild
the Docker image after the change per project convention.
