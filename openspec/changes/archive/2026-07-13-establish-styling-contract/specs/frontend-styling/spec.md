# frontend-styling Delta

## ADDED Requirements

### Requirement: Semantic, themeable markup
Frontend feature markup SHALL be an assumption-free semantic substrate that CSS can restyle in
layout, typography, and color. Singleton regions SHALL carry stable ids; repeated elements SHALL
carry semantic classes named for what they are (not how they look); element state (active, closed,
selected) SHALL be expressed as classes or `data-*` attributes. Markup SHALL NOT contain
presentational-only wrapper elements or structural inline styles; data-driven inline values (e.g. a
marker's category color) are permitted because they carry data, not presentation.

#### Scenario: Repeated element exposes a semantic hook
- **WHEN** a news story or an event is rendered
- **THEN** each is a single element carrying a semantic class (e.g. `story-card`, `event-card`) that
  a stylesheet can target, not a fixed presentational wrapper

#### Scenario: State is targetable by CSS
- **WHEN** a tab, chip, or row is in its active/selected/closed state
- **THEN** that state is reflected by a class or `data-*` attribute on the element, so a stylesheet
  can style the state without inspecting component internals

### Requirement: Global feature-organized stylesheets, no scoped visual styles
All visual styling SHALL live in global stylesheets organized as a base layer plus per-feature
sheets, imported once at the application root, forming the site's single source of visual truth.
Feature components SHALL NOT contain scoped `<style>` blocks for visual styling. Per-feature
stylesheets SHALL style only their own feature's semantic hooks, mirroring the feature-isolation
rule that governs frontend source.

#### Scenario: A feature's visual styling is externally overridable
- **WHEN** a feature's component tree is inspected
- **THEN** it carries no scoped `<style>` block, and its appearance is determined entirely by global
  stylesheets targeting its semantic hooks

#### Scenario: Refactor preserves rendered output
- **WHEN** the app is viewed on the map, news, and events pages before and after the styling
  migration
- **THEN** each page renders visually identically — styles moved to global sheets, output unchanged
