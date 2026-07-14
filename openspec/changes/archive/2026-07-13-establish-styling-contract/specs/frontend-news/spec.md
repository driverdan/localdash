# frontend-news Delta

## ADDED Requirements

### Requirement: Styles via the global styling contract
The news feature SHALL follow the `frontend-styling` contract: its components SHALL carry no scoped
visual `<style>` blocks, all news styling SHALL live in a global news stylesheet targeting the
feature's semantic hooks, and its markup (feed, category tabs, story cards, sources footer) SHALL
expose semantic classes and state attributes rather than presentational wrappers. This migration
SHALL NOT change the feature's rendered appearance.

#### Scenario: News styling is global and externally overridable
- **WHEN** the news feature's components are inspected
- **THEN** none contains a scoped visual `<style>` block, and the feed, tabs, story cards, and
  sources footer render from a global stylesheet targeting their semantic hooks

#### Scenario: News looks identical after migration
- **WHEN** the news page is viewed before and after the migration
- **THEN** it renders visually identically
