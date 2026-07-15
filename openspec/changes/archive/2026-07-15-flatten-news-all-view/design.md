## Context

The news feed's "All" tab renders `news.groupedShown` — a `$derived` in `state.svelte.ts` that
buckets the visible stories into `[slug, label, Story[]]` sections in category display order — and
`NewsFeed.svelte` emits an `<h2 class="section-head">` per non-empty bucket. Category tabs bypass
this and render `news.shownStories` (a flat, filtered list) with no heading.

The API (`app/news/stories.py`) already sorts all stories globally by `latest_published` descending
before returning them, so `news.shownStories` is already in newest-first order for the "All" tab.
The grouping is purely a frontend presentation layer on top of an already-sorted flat list. Each
`StoryCard` already renders a `.badge.cat` category badge, so category context per story does not
depend on the section headings.

## Goals / Non-Goals

**Goals:**
- "All" renders one flat newest-first list with no per-category section headings.
- One section heading at the top names the currently selected tab, on every tab.
- Preserve the existing per-story category badge and tab persistence/fallback behavior.

**Non-Goals:**
- No API, ordering, or clustering changes.
- No change to `StoryCard`, `CategoryTabs`, or the toolbar controls.
- No new sort/filter options for the flat list.

## Decisions

- **Unify the two render branches in `NewsFeed.svelte`.** Replace the `shownTab === "all"` grouped
  loop and the separate category-tab loop with a single path: one `<h2 class="section-head">` bound
  to the selection label, followed by `{#each news.shownStories as story}`. The existing empty-state
  and error branches are unchanged.
- **Drive the heading from a new `shownTabLabel` derived** in `state.svelte.ts`: look up
  `shownTab` in `tabs` and return its label (falls back to the "All" label). This reuses the same
  source of truth the tab bar uses, so the heading and the active tab can never disagree.
- **Delete `groupedShown`.** Once the "All" branch is flat, nothing references it. Removing it keeps
  the store honest about what state the UI actually consumes.
- **Reuse the existing `.section-head` styling** for the single heading rather than introducing a
  new class, keeping the visual treatment consistent with today's category headings.

## Risks / Trade-offs

- **Losing per-category grouping in "All".** Intentional — the flat newest-first stream is the goal,
  and each card's category badge retains per-story context.
- **A heading now appears on category tabs where there was none.** Accepted: it labels the current
  selection and unifies the two code paths, at the cost of one extra line of vertical space.
