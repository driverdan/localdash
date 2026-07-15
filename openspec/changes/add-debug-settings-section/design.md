## Context

Five `localdash.*` localStorage keys shape what the app renders, written through three unrelated paths:

| Key | Written by | Shape | Resurrects when |
| --- | --- | --- | --- |
| `localdash.theme` | `lib/theme.svelte.ts` (own `setItem`) | bare string (`"dark"`) | user changes theme |
| `localdash.map` | `features/timeseries/state.svelte.ts` (`persistPrefs`, persister captured) | `{categories[], showClosed, closedWindow}` | any filter toggle |
| `localdash.map.view` | `MapView.svelte` (raw `savePrefs`) | `{zoom, lat, lng}` | user pans the map |
| `localdash.news` | `features/news/state.svelte.ts` (`persistPrefs`, persister discarded) | `{activeTab, hours, multiOnly}` | tab / hours / multiOnly change |
| `localdash.events` | `features/events/state.svelte.ts` (`persistPrefs`, persister discarded) | `{topics[], maxMiles}` | topic / distance change |

Two properties of the existing system drive this design:

**Key-absence is load-bearing.** `persistPrefs` deliberately skips the save on its first effect run, so a visitor who never changed a preference has no key on disk. For `localdash.map` that absence is the difference between "all categories on, including ones added later" and an allowlist that silently hides new sources. In-memory state and stored state therefore disagree routinely, and the stored side is the one worth showing in a debug tool.

**The namespace is already shell-owned.** `lib/prefs.svelte.ts` defines `loadPrefs`/`savePrefs`/`removePrefs` and the `localdash.*` convention; features only pick a key name and field names. Reading the namespace from shell code is not a feature dependency.

Constraints: `lib/` may not import feature code; styling must use semantic classes in the global stylesheets (no scoped `<style>` in `DebugPanel.svelte`); there is no frontend test runner.

## Goals / Non-Goals

**Goals:**

- See what is actually stored for this browser, from any route, without devtools.
- Delete a single key, so a user stuck in `localdash.map` allowlist mode can recover in-app.
- Zero feature coupling: no feature file changes, no registry, no registration step for future keys.
- Never lie about what happened — the section's display must match storage, including when a delete gets undone.

**Non-Goals:**

- Editing values. Read and delete only.
- Delete-all. Deferred; per-key is the targeted debug operation (clear map filters without losing your theme).
- Live reset of in-memory state on delete. Explicitly rejected below.
- Auto-reload on delete. Explicitly rejected below.
- Backend config (`app/config.py`). There is no server-side or per-account preference storage.
- Labels, descriptions, or schema for known keys. Raw key names and raw values.

## Decisions

### Discover keys by prefix scan, not a registry

Iterate `localStorage` keys and keep those starting with `localdash.`.

*Alternative — feature registry (`registerPrefs({key, label, reset})`), mirroring the existing `registerAction` pattern.* Rejected on two grounds. First, `registerAction` is deliberately **route-aware** (register on mount, unregister on teardown — `debug.svelte.ts:41`), which is exactly wrong here: preferences are global, and you most want to inspect `localdash.news` while standing on `/map`. Second, a registry is a step you can forget — a future key that skips registration becomes invisible and undeletable, whereas a scan finds it for free. The scan also surfaces orphan keys left by older app versions, which a registry structurally cannot.

The cost is no labels and no per-key semantics, which is acceptable for a debug panel.

### List only stored keys; show absence by omission

A prefix scan can only report keys that exist. Rendering "not saved" rows for absent keys would require a hardcoded table of the five key names in shell code — reintroducing exactly the maintenance coupling the scan avoids, and going stale the moment a feature adds a key.

So the section lists what is stored. A browser with nothing stored gets a section-level empty state rather than a hidden section, because "no settings are saved" is a real answer. Absence of one key among several is conveyed by its omission from the list.

### Show stored bytes, not the in-memory model

Render each key's stored value: JSON objects expanded readably, anything else (`localdash.theme`'s bare string, corrupt content) as raw text. Parsing must be tolerant — a corrupt value renders as text rather than erroring, consistent with `loadPrefs`.

Showing in-memory state instead would hide the first-run-doesn't-save behavior and the allowlist semantics — the two things most worth debugging.

### Delete does not reload and does not reset in-memory state

Delete calls `removeItem` for one key. Nothing else.

*Alternative — live reset via `persistPrefs`'s `resetTo(mutate)`.* The primitive exists (`prefs.svelte.ts:52-59, 83-93`) and does the correct dance: suppress saves → mutate state to defaults → `flushSync` → remove the key. But only timeseries captures its persister; news and events **discard** the return value, and `localdash.theme` and `localdash.map.view` never go through `persistPrefs` at all. Wiring live reset for all five keys means changing four feature/shell files, inventing a defaults function per feature, and building the registry this design just rejected.

*Alternative — auto-reload after delete.* Makes delete instantly truthful with no coupling, but a debug panel that navigates the page out from under you is surprising, and it discards the in-memory state you may be mid-way through inspecting.

**Consequence, accepted deliberately:** in-memory state keeps the old values, so deleting has no visible effect, and the owning feature's next persisted-field change rewrites the whole blob — restoring the key with its pre-delete values. `localdash.map.view` is the sharpest case: one map pan rewrites it within seconds.

This is why the **reload to apply** notice exists, and why the deleted row stays visible rather than vanishing. The notice is not decoration around a defect — it is the design telling the truth about a storage-only operation: *the key is gone from disk; the app is still running on the old values; reload to make it real; keep clicking and it will come back.*

### Snapshot on open, not a live subscription

Read storage when the modal opens; mutate only the local view on delete; never poll, never subscribe.

The `storage` event fires for **other** tabs only — a same-tab write is unobservable, so "live" is not actually available without polling. Rather than paper over that with an interval timer, the snapshot is honest at a defined moment. Resurrection then surfaces naturally on reopen: the key is listed again, with its new value and no notice, which is the truth — the delete was undone.

### Where the state lives

The snapshot (scanned entries plus the set of keys deleted this session) belongs in the existing `DebugState` in `lib/debug.svelte.ts`, alongside the `map` and `actions` slices, populated on open. Enumeration itself belongs in `lib/prefs.svelte.ts`, which owns the namespace; the panel should not hand-roll a `localStorage` loop.

### The placeholder becomes route-scoped

Settings is the first always-present section — the map section and actions are both route-gated. `DebugPanel.svelte:57` renders "No debug data for this view" when `!onMap && debug.actions.length === 0`, today reachable only on the 404 route (news and events both register actions). With Settings always rendering, that condition's original justification ("rather than being empty or erroring") is void.

Rather than delete the placeholder, scope it to the route-specific content: the modal is never blank, but "this view publishes no debug data" remains useful signal. The `frontend-debug` requirement is reworded accordingly, keeping the existing DOM condition alive and meaningful.

## Risks / Trade-offs

**A user deletes a key, sees nothing happen, and concludes the button is broken** → The row persists with an explicit "reload to apply" notice. This is the single most important piece of copy in the change; it must state that the deletion applies on reload.

**A user deletes `localdash.map.view` on `/map`, pans, and the key returns** → Unavoidable given no-reload + no-reset. Reopening the panel shows the truth (key present, no notice). Documented as accepted behavior, not a bug to fix later.

**Raw JSON is unfriendly to a non-technical user** → Acceptable: this lives behind a π debug toggle, whose stated purpose is inspecting live UI state.

**Scan picks up a `localdash.` key that is not a preference** → Nothing else writes the namespace today, and the `frontend-preferences` delta makes the prefix a reserved namespace, so this is a spec violation rather than an expected case.

**A stored value is huge and blows out the modal** → The map viewport and filter blobs are small and bounded, but the value display should wrap/scroll within the modal rather than expand it.

**No test runner** → Verification is `npm run check` plus browser-driving each of the five keys, including the resurrection path. Called out explicitly in tasks.
