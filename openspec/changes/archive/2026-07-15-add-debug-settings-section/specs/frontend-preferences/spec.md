## ADDED Requirements

### Requirement: Reserved enumerable preference namespace
The `localdash.` prefix SHALL be a reserved namespace for **all** persisted browser preference state, and SHALL be enumerable so that a reader can list what is stored without knowing the key names in advance.

The namespace SHALL cover every key the frontend persists for a browser, including keys not written through this module's helpers — `localdash.theme` (written directly by the theme module, since theming must apply before first paint) and namespaced view-state keys such as `localdash.map.view`. Any future persisted preference key SHALL use the prefix. A key outside the prefix SHALL NOT be considered preference state and SHALL NOT be enumerated.

This module SHALL expose an enumeration function returning the `localdash.` keys currently present in `localStorage`. Enumeration SHALL report only keys that are actually stored; a key that has never been written SHALL simply be absent from the result, since key-absence is itself meaningful state (for `localdash.map`, an absent key means all categories on, including ones added later, whereas a present key is an allowlist).

Enumeration SHALL be tolerant, consistent with this module's other read paths: if `localStorage` is unavailable or throws, enumeration SHALL yield an empty result rather than propagating an error.

The namespace guarantee exists so shell code can inspect and clear preference state generically — reading the namespace crosses no isolation boundary, because the namespace is owned by this shell module rather than by any feature.

#### Scenario: Enumerates only stored namespace keys
- **WHEN** `localdash.map` and `localdash.theme` are stored, `localdash.news` has never been written, and an unrelated key `other.thing` is stored
- **THEN** enumeration returns `localdash.map` and `localdash.theme`, omitting both `localdash.news` and `other.thing`

#### Scenario: Covers keys not written through the prefs helpers
- **WHEN** the theme module has written `localdash.theme` and the map has written `localdash.map.view`, neither via this module's persist-on-change effect
- **THEN** enumeration includes both keys

#### Scenario: Storage unavailability yields an empty result
- **WHEN** `localStorage` access throws (private mode or storage disabled) and enumeration runs
- **THEN** it returns an empty result and does not error
