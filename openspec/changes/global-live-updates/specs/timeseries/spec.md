## REMOVED Requirements

### Requirement: Live diff WebSocket
**Reason**: Live delivery moves to the global `/api/v1/ws` bus (see the `live-updates` capability): timeseries diffs are now broadcast as `{topic: "timeseries", type: "diff", ...}` messages on the shared endpoint. The per-source `source` query filter is dropped — the bundled frontend (the only consumer) never used it and already filters client-side by selected sources.
**Migration**: Connect to `/api/v1/ws` and handle messages with `topic == "timeseries"`; filter by the message's `source` field client-side if a single-source stream is needed. The `/api/v1/timeseries/ws` endpoint is no longer served.
