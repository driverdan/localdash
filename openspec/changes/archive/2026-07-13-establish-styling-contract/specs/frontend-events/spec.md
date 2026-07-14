# frontend-events Delta

## ADDED Requirements

### Requirement: Styles via the global styling contract
The events feature SHALL follow the `frontend-styling` contract: its components SHALL carry no
scoped visual `<style>` blocks, all events styling SHALL live in a global events stylesheet
targeting the feature's semantic hooks, and its markup (page toolbar, topic chips, event cards)
SHALL expose semantic classes and state attributes rather than presentational wrappers. This
migration SHALL NOT change the feature's rendered appearance.

#### Scenario: Events styling is global and externally overridable
- **WHEN** the events feature's components are inspected
- **THEN** none contains a scoped visual `<style>` block, and the toolbar, chips, and event cards
  render from a global stylesheet targeting their semantic hooks

#### Scenario: Events looks identical after migration
- **WHEN** the events page is viewed before and after the migration
- **THEN** it renders visually identically
