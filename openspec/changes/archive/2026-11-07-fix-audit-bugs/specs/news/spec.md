## ADDED Requirements

### Requirement: Registry sync removes dropped sources
At application startup, registry sync SHALL delete every news source row whose slug is not in the
code registry. Its feeds and articles SHALL be removed through the existing `ON DELETE CASCADE`
foreign keys, with no migration. A removed outlet SHALL no longer be fetched, listed by
`GET /api/v1/news/sources`, or included in stories. Sources still in the registry SHALL be
unaffected.

#### Scenario: A source removed from the registry is deleted
- **WHEN** the application starts after an outlet was removed entirely from the registry
- **THEN** its `news_sources` row, feeds, and articles are deleted, and it is neither fetched nor
  listed

#### Scenario: Registered sources are untouched
- **WHEN** registry sync runs with every stored source still present in the registry
- **THEN** no source rows are deleted
