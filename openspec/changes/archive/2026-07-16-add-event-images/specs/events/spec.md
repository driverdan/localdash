# events — delta for add-event-images

## ADDED Requirements

### Requirement: Per-event images
`RawEvent` SHALL carry an optional `image_url` field, and each source SHALL supply it when its
upstream payload has a usable per-event image: CitySpark from `MediumImg` (falling back to
`LargeImg`, then `SmallImg`, then the first `Images[].url`), CarCruiseFinder from the JSON-LD
`image` property, Meetup from the event photo in its GraphQL selection, and iCal feeds from an
image `ATTACH` property. A generic/placeholder image — one whose URL basename matches a
case-insensitive generic/placeholder/default/stock pattern (e.g. the Cars and Coffee feed's
`Generic-Car-Show.jpg`) — SHALL be treated as absent; the exclusion helper SHALL be shared by all
sources. The canonical `Event` SHALL persist a single nullable `image_url`: a newly created event
takes the raw event's image, and both the ingest merge path and stored-event reconciliation SHALL
backfill `image_url` only when the stored value is null (an existing image is never overwritten).
The events listing API SHALL serialize `image_url` (null when absent) on every item. Images are
hotlinked source URLs; the system SHALL NOT download or store image content.

#### Scenario: Source-supplied image is stored and served
- **WHEN** a CitySpark event whose payload carries a `MediumImg` URL is ingested as a new event
- **THEN** the stored event's `image_url` is that URL and the listing API returns it on the item

#### Scenario: Generic placeholder images are ignored
- **WHEN** an iCal `VEVENT` carries an image `ATTACH` whose filename matches the
  generic/placeholder pattern (e.g. `Generic-Cruise-Night.jpg`)
- **THEN** the raw event has no image and the stored event's `image_url` remains null

#### Scenario: Merge backfills a missing image only
- **WHEN** a source reports an event that de-duplicates onto a stored event with a null
  `image_url` and supplies an image
- **THEN** the stored event's `image_url` is backfilled with the reported URL

#### Scenario: An existing image is never overwritten
- **WHEN** a source reports an image for an event that already has a non-null `image_url`
- **THEN** the stored `image_url` is unchanged

#### Scenario: Events without images serialize null
- **WHEN** the listing API returns an event no source supplied an image for
- **THEN** the item's `image_url` is null and the response is otherwise unchanged
