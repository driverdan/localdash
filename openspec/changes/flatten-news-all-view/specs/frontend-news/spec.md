## MODIFIED Requirements

### Requirement: Category tabs with grouped All view
The feed SHALL offer an "All" tab plus one tab per category present in the loaded stories (in the
API's category display order). A category tab SHALL show only that category's stories; the "All"
tab SHALL show every category's stories as a single flat list in the newest-activity-first order the
API returns, not grouped under category section headings. A single section heading at the top of the
feed SHALL name the currently selected tab (the "All" label, or the selected category's label) on
every tab. The active tab SHALL persist in `localdash.news` and restore on load; if the saved tab
is not among the available tabs once stories load, the feed SHALL display the "All" tab instead.

#### Scenario: All view is one flat newest-first list
- **WHEN** the "All" tab is active and stories span three categories
- **THEN** the feed shows a single "All" heading followed by every story in one flat list ordered
  newest activity first, with no per-category section headings

#### Scenario: Category tab filters
- **WHEN** the user selects the Sports tab
- **THEN** the feed shows a single "Sports" heading followed by only sports stories, ungrouped

#### Scenario: Active tab survives a reload
- **WHEN** the user selects the Sports tab and reloads the page
- **THEN** the Sports tab is active once stories load

#### Scenario: Saved tab with no stories falls back to All
- **WHEN** the saved active tab names a category absent from the loaded stories
- **THEN** the feed displays the "All" view
