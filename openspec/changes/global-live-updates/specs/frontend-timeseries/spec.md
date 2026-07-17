## MODIFIED Requirements

### Requirement: Live updates over WebSocket
The feature SHALL subscribe to the `timeseries` topic on the shared live-update bus (see `frontend-live`; unfiltered — every source) and apply each diff incrementally:
`new` and `updated` features upsert into state, `closed` ids either disappear (default) or flip to
muted closed styling (when show-closed is on); diffs from unselected sources are ignored. The
subscription SHALL be mount-scoped: registered when the dashboard mounts and disposed on unmount.
The connection indicator SHALL reflect the shared bus connection state (the bus owns reconnection;
the feature SHALL NOT open its own socket), and on a bus reconnect while mounted the feature SHALL
reload active entities to recover diffs missed while disconnected. Applying a diff SHALL NOT require
refetching or re-rendering unaffected entities.

#### Scenario: Diff applies incrementally
- **WHEN** a poll cycle produces a diff with one new and one closed entity
- **THEN** the new entity's marker and row appear and the closed entity disappears (or turns muted
  when show-closed is on), without a full reload

#### Scenario: Muted source diffs are ignored
- **WHEN** a diff arrives for a source the user has unchecked
- **THEN** the UI state does not change

#### Scenario: Reconnect after disconnect
- **WHEN** the shared connection closes unexpectedly while the dashboard is mounted
- **THEN** the indicator shows the disconnected state, the bus reconnects automatically, and on
  reconnect the feature reloads active entities so no missed diffs are lost
