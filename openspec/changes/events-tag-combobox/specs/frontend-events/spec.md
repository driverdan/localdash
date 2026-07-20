## MODIFIED Requirements

### Requirement: Topic, distance, and search filtering
The events page SHALL offer a topic **combobox** (candidates from `GET /api/v1/events/tags`,
multi-select), a maximum distance control, and a title search box. The topic combobox SHALL be a
text input that filters a suggestion dropdown: when the input is empty and focused it SHALL list the
full known-tag set, and typing SHALL refine the suggestions by case-insensitive substring match,
excluding tags already selected. Selecting a suggestion SHALL add that topic; selected topics SHALL
render as removable pills adjacent to the input, and removing a pill SHALL clear that topic. Only
tags present in the known set MAY be selected — text that matches no known tag SHALL NOT commit a
topic. Changing any filter SHALL refetch `GET /api/v1/events/items` with the corresponding query
parameters (server-side filtering), and active filters SHALL be visually indicated. Selected topics
and the maximum distance SHALL persist in `localdash.events` and restore on load (saved topics
intersected with the currently available tags); the search box SHALL NOT persist and starts empty on
every load.

The topic combobox SHALL be keyboard-operable with accessible combobox semantics: ArrowUp/ArrowDown
SHALL move the active suggestion, Enter SHALL commit the active suggestion, Escape SHALL close the
dropdown, and Backspace on an empty input SHALL remove the last selected pill. The input SHALL expose
ARIA combobox semantics and the suggestion list SHALL expose listbox/option roles with the active
option indicated.

#### Scenario: Empty combobox lists all tags
- **WHEN** the user focuses the topic combobox without typing
- **THEN** the dropdown lists every known tag except those already selected

#### Scenario: Typing filters the suggestions
- **WHEN** the user types "mu" in the topic combobox
- **THEN** the dropdown shows only known tags whose name contains "mu" (case-insensitive), excluding
  already-selected tags

#### Scenario: Selecting a tag filters server-side
- **WHEN** the user selects the `music` suggestion and then the `food` suggestion
- **THEN** each becomes a removable pill and the list refetches with `topic=music&topic=food`,
  showing only matching events

#### Scenario: Removing a pill clears its topic
- **WHEN** the user removes the `music` pill
- **THEN** `music` is no longer an active topic and the list refetches without `topic=music`

#### Scenario: Unknown text cannot be committed
- **WHEN** the user types "notarealtag" (matching no known tag) and presses Enter
- **THEN** no pill is added and the active topics are unchanged

#### Scenario: Keyboard navigation and selection
- **WHEN** the user presses ArrowDown to highlight a suggestion and then Enter
- **THEN** the highlighted tag is added as a pill and the list refetches with that topic

#### Scenario: Distance filter
- **WHEN** the user sets a 15-mile maximum
- **THEN** the list refetches with `max_miles=15` and unlocated events disappear from the list

#### Scenario: Search filter
- **WHEN** the user types "jazz" in the search box
- **THEN** the list refetches with `search=jazz` and shows only title matches

#### Scenario: Topic and distance selections survive a reload
- **WHEN** the user selects the `music` tag, sets a 15-mile maximum, and reloads the page
- **THEN** a `music` pill is present, the distance control shows 15 miles, and the initial fetch
  carries `topic=music&max_miles=15`

### Requirement: Styles via the global styling contract
The events feature SHALL follow the `frontend-styling` contract: its components SHALL carry no
scoped visual `<style>` blocks, all events styling SHALL live in a global events stylesheet
targeting the feature's semantic hooks, and its markup (page toolbar, topic combobox with its
dropdown and selected pills, event cards) SHALL expose semantic classes and state attributes rather
than presentational wrappers.

#### Scenario: Events styling is global and externally overridable
- **WHEN** the events feature's components are inspected
- **THEN** none contains a scoped visual `<style>` block, and the toolbar, topic combobox (dropdown
  and pills), and event cards render from a global stylesheet targeting their semantic hooks
