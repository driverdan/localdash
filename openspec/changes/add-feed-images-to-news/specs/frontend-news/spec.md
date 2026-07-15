## MODIFIED Requirements

### Requirement: Story feed rendering
The feed SHALL render one card per story from `GET /api/v1/news/stories`: category badge, a
source badge showing "N sources" (visually distinguished) for multi-outlet stories or the single
outlet's name otherwise, relative time since latest activity, the story's `image_url` as a lead
image when present (and nothing in its place when absent — no placeholder), the headline linking to
the first outlet's article (new tab), the summary when present, and one link pill per outlet (outlet
name, that outlet's own headline as hover title, opening in a new tab). Stories SHALL appear newest
activity first. An empty result SHALL show an empty-state message, and a failed load an error
message.

#### Scenario: Multi-source story card
- **WHEN** a story has articles from three outlets
- **THEN** its card shows a "3 sources" badge and three outlet link pills, each opening that
  outlet's article in a new tab

#### Scenario: Failed load is visible
- **WHEN** the stories request fails
- **THEN** the feed area shows an error message instead of stale or blank content

#### Scenario: Story with an image shows it
- **WHEN** a story has a non-null `image_url`
- **THEN** its card renders that image

#### Scenario: Story without an image shows no placeholder
- **WHEN** a story's `image_url` is null
- **THEN** its card renders with no image element and no placeholder in its place
