## Why

The news "All" tab splits stories into a section heading per category, breaking the single
newest-first stream the API already returns and pushing recent stories down under later category
headings. A reader scanning "All" wants one chronological list, not a per-category digest — the
category context is already carried by each story card's badge.

## What Changes

- The "All" tab renders a single flat list of stories in global newest-first order, instead of
  grouping them under per-category section headings.
- A single section heading at the top of the feed shows the currently selected tab's label
  ("All", or the chosen category) on every tab, replacing the per-category headings.
- Category tabs continue to filter to a single category; they now also carry the top section
  heading naming the selection.
- Each story card keeps its existing category badge, so per-story category context is preserved in
  the flat "All" list.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `frontend-news`: The "All" view no longer groups stories under per-category section headings;
  it renders one global newest-first list under a single heading naming the selected tab.

## Impact

- `frontend/src/features/news/components/NewsFeed.svelte`: collapse the grouped "All" branch into a
  single flat list with one selection heading.
- `frontend/src/features/news/state.svelte.ts`: remove the now-dead `groupedShown` derived; add a
  small `shownTabLabel` derived to feed the heading.
- `StoryCard.svelte` and the category tabs are unchanged.
