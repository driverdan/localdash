## 1. TagCombobox component

- [ ] 1.1 Add `frontend/src/features/events/components/TagCombobox.svelte` with props: `candidates: string[]`, `selected: string[]`, and `onToggle: (tag: string) => void`
- [ ] 1.2 Hold local UI state only: query text, open/closed flag, active-suggestion index
- [ ] 1.3 Derive the suggestion list via `$derived`: `candidates` minus `selected`, then case-insensitive substring match on the query (full list when query is empty)
- [ ] 1.4 Render selected tags as removable pills, each with a labeled remove button that calls `onToggle(tag)`
- [ ] 1.5 Render the text input and the suggestion dropdown; clicking a suggestion calls `onToggle(tag)`, clears the query, and keeps focus in the input
- [ ] 1.6 Commit suggestion selection on pointerdown/mousedown so it fires before input blur closes the dropdown

## 2. Keyboard and accessibility

- [ ] 2.1 Input carries `role="combobox"`, `aria-expanded`, `aria-controls`, and `aria-activedescendant`; dropdown is `role="listbox"` with `role="option"` items and a stable id per option
- [ ] 2.2 ArrowDown/ArrowUp move the active index (clamped); Enter commits the active suggestion; Escape closes the dropdown
- [ ] 2.3 Backspace on an empty query removes the last selected pill (via `onToggle`)
- [ ] 2.4 Close the dropdown when focus leaves the whole component (outside click / focus-out), reopen on focus/typing
- [ ] 2.5 Guarantee known-list-only: never commit query text directly — only a tag drawn from the derived suggestions can be selected

## 3. Wire into the Events page

- [ ] 3.1 In `EventsPage.svelte`, replace the `{#if events.tags.length > 0}` chip block with `<TagCombobox candidates={events.tags} selected={events.topics} onToggle={toggleTopic} />`
- [ ] 3.2 Keep the existing `toggleTopic` handler (calls `events.toggleTopic` then `loadItems`) and the empty-state copy keyed off topics/search/maxMiles
- [ ] 3.3 Confirm `loadTags` pruning, `localdash.events` persistence, and live-reload behavior are unchanged

## 4. Styling

- [ ] 4.1 Add combobox, dropdown, suggestion, and pill styles to `frontend/src/styles/events.css` targeting semantic hooks (no scoped `<style>` in the component)
- [ ] 4.2 Style active-suggestion and pill states; ensure dark theme via existing theme tokens
- [ ] 4.3 Remove the now-unused chip styles from the events stylesheet

## 5. Verify

- [ ] 5.1 Run `npm run check` / lint in `frontend/` and fix any type or a11y issues
- [ ] 5.2 Rebuild the Docker image (`docker compose up --build`) and manually verify: empty focus lists all tags, typing filters, selecting filters events server-side, pill removal refetches, unknown text cannot commit, keyboard nav works, and selections survive a reload
