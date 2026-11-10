## ADDED Requirements

### Requirement: Scheduled refresh jobs share one registration contract
The system SHALL run every background refresh as an in-process scheduled job registered under a
stable id:

- one job per registered timeseries collector, with id equal to the collector's source key and
  interval equal to its poll interval;
- `news_refresh` every `news_refresh_minutes`, only when `news_enabled`;
- `events_refresh` every `events_refresh_minutes`, only when `events_enabled`;
- `weather_refresh` every `weather_cache_minutes`, only when `weather_enabled`.

Every job SHALL run once immediately at startup and then on its interval. A job SHALL NOT run
concurrently with itself, and missed ticks SHALL collapse into a single run rather than queue up.
All jobs SHALL be registered with these same options. The scheduler SHALL NOT contain any
refresh cycle's logic: no locks, sessions or signal decisions. It SHALL only invoke the refresh
entry point that the scheduled and manual triggers share.

#### Scenario: Enabled features each get one job
- **WHEN** the application starts with news, events and weather enabled and four collectors
  registered
- **THEN** jobs `hc911`, `tdot`, `epb`, `tnaw`, `news_refresh`, `events_refresh` and
  `weather_refresh` are scheduled, each with its configured interval

#### Scenario: Disabled feature schedules nothing
- **WHEN** the application starts with `weather_enabled=false`
- **THEN** no `weather_refresh` job is scheduled and every other job is unaffected

#### Scenario: Every job runs at startup
- **WHEN** the scheduler starts
- **THEN** every registered job's first run is scheduled for the moment of startup rather than one
  interval later

#### Scenario: A slow tick does not overlap the next
- **WHEN** a job's cycle is still running when its next tick comes due
- **THEN** no second instance starts, and the overdue ticks result in at most one further run

### Requirement: A failed refresh job never stops scheduling
A refresh job whose cycle raises SHALL have the failure logged with the job's id, and SHALL leave
the scheduler, its own future ticks and every other job running. The next tick SHALL retry the
cycle normally.

#### Scenario: Failing job is logged and retried
- **WHEN** the news refresh cycle raises during a scheduled tick
- **THEN** the error is logged with the job id `news_refresh`, no exception escapes the job, and
  the next `news_refresh` tick runs a fresh cycle

#### Scenario: One failing job does not affect others
- **WHEN** the weather refresh fails on every tick
- **THEN** the collector, news and events jobs keep running on their own intervals
