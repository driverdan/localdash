## ADDED Requirements

### Requirement: Closure sweep and run telemetry
Each collection cycle SHALL treat the collector's payload as the complete set of currently active
entities for its source. Every active entity of that source that is absent from the payload SHALL
be closed: it is marked inactive, its `last_seen_at` is set to the time of closure (which is what
`closed_within` measures), and a final observation is recorded with status `Closed`, its last
geometry, and `properties: {"reason": "absent_from_feed"}`. Consequently, a successful fetch whose
payload normalizes to no observations SHALL close every active entity of that source; only a raised
fetch or parse error leaves entities untouched. Every registered collector SHALL run one cycle
immediately at startup and then on its poll interval. A failed cycle's error text SHALL pass
through credential redaction before it is persisted to `sources.last_error` or served by the
sources endpoint.

#### Scenario: Absent entity is closed
- **WHEN** an active entity is missing from a source's next payload
- **THEN** it becomes inactive with `last_seen_at` set to the closure time, a `Closed` observation
  with reason `absent_from_feed` is recorded, and its id is broadcast in the diff's `closed` list

#### Scenario: Empty payload closes the source's entities
- **WHEN** a collector's fetch succeeds but its payload yields no observations
- **THEN** every active entity of that source is closed

#### Scenario: Fetch error leaves entities untouched
- **WHEN** a collector's fetch raises an error
- **THEN** no entity is closed and the run is recorded with status `error`

#### Scenario: Error telemetry is redacted
- **WHEN** a collector fails with an error message containing a credential (e.g. a token in a URL)
- **THEN** the persisted and served `last_error` shows the credential masked
