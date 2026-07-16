# frontend-styling Specification

## Purpose

The site-wide styling contract every frontend feature follows: semantic markup hooks, global
feature-organized stylesheets, no scoped visual styles, and assumption-free markup — the substrate
that makes the UI restyleable in layout, typography, and color. The timeseries/map feature is the
reference implementation; news and events conform to it.

## Requirements

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

### Requirement: Design-token layer
The base stylesheet SHALL define a design-token layer: CSS custom properties on `:root` covering
the site's shared color values (brand/primary, text tiers, links, surfaces, borders, status
colors, on-primary variants) and font stacks. Global stylesheets SHALL consume these tokens via
`var(--…)` rather than repeating raw color values; a shared color SHALL have exactly one defining
declaration. Data-driven inline values (e.g. a map marker's category color) and genuinely local
one-off values remain permitted outside the token layer.

#### Scenario: Retheming is a token edit
- **WHEN** a token value (e.g. the primary brand color) is changed in the `:root` block
- **THEN** every element styled from that token re-colors, with no other stylesheet edits

#### Scenario: No duplicated brand values
- **WHEN** the global stylesheets are searched for the raw hex value of a token-covered color
- **THEN** it appears only in token definitions (`:root` or a theme's override block), not inline
  in feature rules

### Requirement: Chattanooga-derived visual identity
The default theme's palette and typography SHALL follow chattanooga.gov's design language: deep
navy primary (`#004360`) rendered as light text on the colored header, steel-blue links, near-black
navy body text, and the city site's green/red/amber accent family — while keeping the existing
shell structure and dashboard density.

#### Scenario: Header carries the civic palette
- **WHEN** the site loads with the default theme
- **THEN** the header is the deep navy primary with light text and navigation, in the same
  header structure as before the restyle

#### Scenario: Status colors stay legible on the navy header
- **WHEN** the header status bar shows its ok or error state
- **THEN** it uses bright on-primary variants that meet contrast against the navy, not the darker
  brand green/red used on light surfaces

### Requirement: Self-hosted typography
The site SHALL bundle its webfonts (a heading face and a body face) through the frontend build so
they are served from the app's own origin; pages SHALL NOT request fonts from external hosts. Font
stacks SHALL include system fallbacks so text renders before or without the webfonts.

#### Scenario: No external font requests
- **WHEN** any page loads
- **THEN** all font files are served from the app's own origin, with no requests to external font
  CDNs

#### Scenario: Heading and body faces are distinct
- **WHEN** a page with headings and body text renders
- **THEN** headings use the heading font stack and body text the body font stack, each falling
  back to system fonts if the webfont is unavailable
