## ADDED Requirements

### Requirement: Global icon module
The frontend SHALL provide a single global icon module at `src/lib/icons/` that any feature can import, backed by one registry mapping stable icon names to bundled Lucide icon data. The module SHALL depend on locally bundled assets only (no CDN or network fetch), and SHALL include only the icons referenced by the registry so unused icons are tree-shaken from the build.

#### Scenario: A feature imports an icon by name
- **WHEN** a feature imports an icon by its registry name
- **THEN** the icon resolves from the local bundle with no network request

#### Scenario: Only registered icons are bundled
- **WHEN** the frontend is built
- **THEN** only icons referenced by the registry are included and the remainder of the icon library is excluded

### Requirement: Two render paths from one registry
The icon module SHALL expose two render paths backed by the same registry: an `iconSvg(name, options)` helper returning an SVG string suitable for imperative/HTML contexts (e.g. Leaflet `divIcon`), and an `Icon` Svelte component for use in templates. Both SHALL accept configurable color and size, and SHALL produce visually identical output for the same name and options.

#### Scenario: SVG string for an HTML/imperative context
- **WHEN** a caller invokes `iconSvg` with a name, color, and size
- **THEN** it returns an SVG string rendered in that color and size, usable directly as marker HTML

#### Scenario: Component for a template context
- **WHEN** the `Icon` component is used in a Svelte template with a name, color, and size
- **THEN** it renders the same glyph as `iconSvg` would for those options

#### Scenario: Configurable color
- **WHEN** a caller requests the same icon with two different colors
- **THEN** the rendered glyph reflects each requested color respectively
