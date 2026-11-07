## ADDED Requirements

### Requirement: Tests do not depend on the date they run

A test's result SHALL NOT change as the calendar advances. A test that exercises behavior relative
to the current time (for example, the events reconciliation pass, which only considers events
starting at or after now) SHALL either compute its dates from the current time or pass a fixed
"now" into the code under test. Fixed calendar dates SHALL be used only where the code under test
does not compare them against the current time.

#### Scenario: Reconcile tests seed upcoming events

- **WHEN** a test seeds events for `reconcile_events()` to merge
- **THEN** the seeded start times are computed as a future offset from the current time
- **AND** the test passes regardless of the date it runs on

#### Scenario: Time-independent tests keep fixed dates

- **WHEN** a test exercises code that never compares event dates to the current time (for example,
  `upsert_raw_events()` de-duplication)
- **THEN** the test may use fixed calendar dates, including dates in the past
