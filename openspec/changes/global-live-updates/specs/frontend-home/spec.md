## ADDED Requirements

### Requirement: Widgets refresh on live update signals
The home feature SHALL keep its widgets current via permanent subscriptions on the shared
live-update bus (see `frontend-live`), registered from the app shell: a `news` ping refetches the
stories digest, an `events` ping refetches the events digest, and a `weather` ping refetches the
weather strip. The same loaders SHALL run on bus reconnect. On-mount initial fetches and the
per-widget loaded/error flags are unchanged — a live refetch that fails leaves the previous widget
content in place rather than blanking it.

#### Scenario: Digest updates without a reload
- **WHEN** the user is viewing `/` and a news refresh cycle completes server-side
- **THEN** the stories digest refetches and shows the new stories without a page reload or
  navigation

#### Scenario: Weather strip follows the weather ping
- **WHEN** a `{topic: "weather", type: "updated"}` message arrives
- **THEN** the weather strip refetches `/api/v1/weather/current` and renders the fresh conditions

#### Scenario: Failed live refetch keeps previous content
- **WHEN** a ping-triggered digest refetch fails
- **THEN** the widget keeps showing its previous content
