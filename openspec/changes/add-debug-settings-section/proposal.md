## Why

The browser holds five `localdash.*` localStorage keys that silently shape what the app shows — filters, tabs, time windows, map viewport, theme — and today there is no way to see them or clear them from inside the app. Diagnosing "why does this user see something different?" means opening devtools; recovering from a bad stored state means knowing the key names by heart.

This is worse than it sounds because **key-absence is load-bearing, not just an empty value**. For `localdash.map`, a saved category list is an *allowlist* that replaces the all-on default, so categories added to the app later start unchecked; only deleting the key restores dynamic defaults. A user can be stuck missing new map sources with no in-app way to see why or fix it.

## What Changes

- Add an always-present **Settings** section to the shell debug modal, listing every `localdash.*` key found in `localStorage` with its stored value.
- The section shows **stored bytes, not in-memory state**. It lists exactly the keys that are stored — absence is shown by omission, and a browser with nothing stored gets an explicit empty state rather than a hidden section, because "no settings saved" is itself the answer someone opens the panel to get.
- Each row gets a **per-key Delete control**. Delete removes only that key.
- Delete **does not reload the page and does not reset in-memory state**; the deleted row stays visible showing a `reload to apply` notice. Deleting is a storage operation, not a live reset.
- The section is discovered by **scanning `localStorage` for the `localdash.` prefix** — no feature registry, no feature imports, and future keys appear with no registration step.
- **BREAKING (spec-level, not runtime):** the debug modal's "no debug data for this view" placeholder becomes unreachable, since Settings always renders. The existing `frontend-debug` scenario asserting that placeholder must be reworked.
- Elevate the `localdash.` prefix from an informal naming convention into a **reserved, enumerable namespace** that all persisted browser preference state must use.

## Capabilities

### New Capabilities

None. A Settings section is exactly what the `frontend-debug` overlay is structured to accept ("new sections can be added without touching existing ones"), and the namespace guarantee belongs to the module that already owns the keys. Inventing a new capability here would split the debug overlay's spec across two files for no gain.

### Modified Capabilities

- `frontend-debug`: adds a Settings section requirement (enumerate stored preference keys, show stored values, per-key delete, reload-to-apply notice, snapshot-on-open read model). Reworks the **Route-aware debug sections** requirement, whose placeholder scenario can no longer occur once a shell section is always present.
- `frontend-preferences`: adds a requirement that `localdash.` is a reserved, enumerable namespace covering **all** persisted browser preference state — including keys not written through `prefs.svelte.ts` (`localdash.theme`, `localdash.map.view`) — and that the module exposes enumeration so a reader can list stored keys without knowing them in advance.

## Impact

**Affected code**

- `frontend/src/lib/prefs.svelte.ts` — new enumeration primitive (list `localdash.*` keys present in storage); `removePrefs` gains an external caller.
- `frontend/src/lib/DebugPanel.svelte` — new Settings section; placeholder condition revised.
- `frontend/src/lib/debug.svelte.ts` — possible state slice for the panel's storage snapshot and per-key deleted flags (see design.md).
- `frontend/src/styles/base.css`, `frontend/src/styles/theme-dark.css` — semantic classes for the new section, per the styling contract (no scoped `<style>` in `DebugPanel.svelte`).

**Explicitly not affected**

- No feature code changes. `features/news`, `features/events`, `features/timeseries`, and `lib/theme.svelte.ts` are untouched — the shell already owns the `localdash.*` namespace, so reading it crosses no isolation boundary.
- Backend config (`app/config.py`, pydantic-settings) is out of scope. There is no server-side or per-account preference storage.

**Verification**

No frontend test runner exists (`frontend/package.json` defines only `check` and `format`). Verification is `npm run check` plus driving the panel in a browser against each of the five keys.
