## MODIFIED Requirements

### Requirement: Permanent feature subscriptions registered from the shell
The app shell SHALL start the connection and register each feature's live subscriptions once at
startup. News, events, and home subscriptions SHALL be permanent (not tied to route mounts),
refetching into their module-singleton stores so any route is current when navigated to; home's
permanent subscriptions include a `timeseries`-topic subscription filtered to `epb`-source
diffs for the outages digest. The map's `timeseries` subscription SHALL remain route-scoped,
using the same bus with mount-scoped disposers — one topic may carry both permanent and
mount-scoped subscribers.

#### Scenario: Background route stays fresh
- **WHEN** the user is on `/map` and a `news` ping arrives
- **THEN** the news store refetches in the background, and navigating to `/news` shows the new stories without waiting for a fetch triggered by the navigation

#### Scenario: Subscriptions do not accumulate
- **WHEN** the user navigates between routes repeatedly
- **THEN** permanent subscriptions are registered exactly once and mount-scoped subscriptions are disposed on unmount

#### Scenario: One topic serves permanent and route-scoped subscribers
- **WHEN** the user is not on `/map` and a `timeseries` diff with source `epb` arrives
- **THEN** home's permanent subscription refetches the outages digest while no map handler runs
