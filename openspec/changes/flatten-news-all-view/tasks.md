## 1. Store: flat-list state

- [ ] 1.1 In `frontend/src/features/news/state.svelte.ts`, add a `shownTabLabel` `$derived` that
  returns the label of `shownTab` from `tabs` (falling back to the "All" label).
- [ ] 1.2 Remove the now-dead `groupedShown` `$derived` from the same file.

## 2. Feed: single heading + flat list

- [ ] 2.1 In `frontend/src/features/news/components/NewsFeed.svelte`, replace the
  `shownTab === "all"` grouped branch and the separate category-tab branch with a single path:
  one `<h2 class="section-head">{news.shownTabLabel}</h2>` followed by
  `{#each news.shownStories as story (story.id)}<StoryCard {story} />{/each}`.
- [ ] 2.2 Leave the loading, error, and empty-state branches unchanged; confirm the `StoryCard`
  category badge and `CategoryTabs` are untouched.

## 3. Verify

- [ ] 3.1 Run `npm run check` (svelte-check must stay at 0 errors); grep the news feature for any
  remaining `groupedShown` references.
- [ ] 3.2 Run `npm run build`, load `/`, and confirm: "All" shows one flat newest-first list under an
  "All" heading with per-story category badges; a category tab shows only its stories under a heading
  naming it; selecting a tab and reloading restores it.
