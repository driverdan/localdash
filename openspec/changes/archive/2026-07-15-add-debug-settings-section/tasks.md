## 1. Namespace enumeration (`lib/prefs.svelte.ts`)

- [x] 1.1 Export a `PREFS_PREFIX = "localdash."` constant and an enumeration function returning the prefix's keys currently present in `localStorage`, each with its raw stored string.
- [x] 1.2 Wrap enumeration in try/catch returning an empty result when storage throws (private mode / disabled), matching the module's existing swallow-on-failure reads.
- [x] 1.3 Sort the result by key name so the panel's row order is stable across opens.
- [x] 1.4 Add a module comment noting the prefix is a reserved namespace covering keys not written through this module (`localdash.theme`, `localdash.map.view`), per the `frontend-preferences` delta.

## 2. Debug store slice (`lib/debug.svelte.ts`)

- [x] 2.1 Add a settings slice: the snapshot of enumerated entries plus the set of keys deleted this session.
- [x] 2.2 Add a method that (re)reads the snapshot via the prefs enumeration and clears the deleted-key set — this is the "snapshot on open" entry point.
- [x] 2.3 Add a delete method that calls `removePrefs(key)`, marks the key deleted in the session set, and leaves the snapshot row in place (row stays visible with its value).
- [x] 2.4 Keep the slice feature-agnostic — `lib/` imports no feature code.

## 3. Take the snapshot on open

- [x] 3.1 Refresh the snapshot whenever the modal transitions closed → open (covers both the π toggle and any other open path), not on every render.
- [x] 3.2 Verify a key resurrected by a same-tab write appears with its new value and no reload notice after close + reopen.

## 4. Settings section UI (`lib/DebugPanel.svelte`)

- [x] 4.1 Render an always-present Settings section, outside the `onMap` / actions route gating.
- [x] 4.2 Render one row per snapshot entry: key name, stored value, and a delete control.
- [x] 4.3 Render values tolerantly — pretty-print parsed JSON objects; show non-object and unparseable values (`localdash.theme`'s bare string, corrupt content) as raw text. Never throw.
- [x] 4.4 Show a "reload to apply" notice on rows deleted this session, with copy stating the deletion applies on reload.
- [x] 4.5 Render an explicit empty state when no `localdash.` key is stored (do not hide the section).
- [x] 4.6 Rework the placeholder condition so "No debug data for this view" scopes to the route-specific content and renders beside the Settings section rather than standing in for the whole modal.

## 5. Styling (`styles/base.css`, `styles/theme-dark.css`)

- [x] 5.1 Add semantic classes for the settings rows, value blocks, delete control, notice, and empty state — global stylesheets only, no scoped `<style>` in `DebugPanel.svelte`.
- [x] 5.2 Constrain value display to wrap/scroll inside the modal so a long value cannot blow out its width.
- [x] 5.3 Add dark-theme variants and confirm the section is legible in both themes.

## 6. Verification (no test runner — `check` + browser)

- [x] 6.1 `npm run check` passes (`svelte-check`); `npm run format` leaves no diff.
- [x] 6.2 Rebuild via `docker compose up --build` and drive the panel in a browser.
- [x] 6.3 With all five keys stored, confirm each is listed from a route it does not belong to (e.g. `localdash.news` visible on `/map`).
- [x] 6.4 Confirm `localdash.theme` renders as a bare string and a hand-corrupted key renders as raw text without erroring.
- [x] 6.5 Delete one key; confirm only that key is removed, the page does not reload, the app is visually unchanged, and the row shows the reload notice.
- [x] 6.6 Delete `localdash.map` and reload without touching a filter; confirm the map returns to all-categories-on defaults.
- [x] 6.7 Delete `localdash.map.view`, close the panel, pan the map, reopen; confirm the key is listed again with a new value and no notice (documented resurrection path).
- [x] 6.8 Clear all `localdash.` keys and confirm the section shows its empty state.
- [x] 6.9 Confirm the route placeholder still renders on an unknown route (e.g. `/foo`) alongside the Settings section.

## 7. Spec sync

- [x] 7.1 Run `openspec validate --change add-debug-settings-section` and resolve any findings.
- [x] 7.2 Confirm the `frontend-debug` MODIFIED requirement matches the archived main spec's requirement header exactly, so the delta applies cleanly at archive time.
