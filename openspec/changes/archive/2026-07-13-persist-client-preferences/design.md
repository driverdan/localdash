# Design: persist-client-preferences

## Context

The frontend is a Svelte 5 SPA with a History-API router; feature state lives in module-level
singleton classes (`ts`, `events`, `news`) using `$state`/`$derived` and `SvelteSet`/`SvelteMap`.
Because the singletons live for the page lifetime, selections already survive in-app navigation —
the only losses happen on a full page load (refresh, new tab). Nothing in the frontend touches
`localStorage` today.

Two categories of state exist in each store: durable "preferences" (which sources to show, time
windows, toggles) and ephemeral/live state (search text, dropdowns derived from loaded data, open
detail panel, fetched items, connection status). Only the first category should persist.

## Goals / Non-Goals

**Goals:**

- Preferences survive page reloads with no backend involvement.
- First-visit behavior is unchanged (everything defaults on).
- Saved source/category selections behave as an explicit allowlist: new sources or categories
  shipped later default to unchecked for users with saved preferences.
- Corrupt, stale, or unknown stored data can never break page load.
- A user can return to dynamic-default behavior ("Reset filters").

**Non-Goals:**

- No server-side or per-account preference storage; preferences are per-browser.
- No persistence of ephemeral state: `search`, `status`, `jurisdiction`, `detailId`, fetched data,
  connection state.
- No URL-parameter encoding of view state (shareable links are a separate concern).
- No cross-tab live sync (`storage` events); tabs read preferences at load only.

## Decisions

### 1. localStorage, one JSON key per feature

Keys: `localdash.map`, `localdash.events`, `localdash.news`, each holding one JSON object of that
feature's persisted fields.

- *Why localStorage over URL params*: preferences must apply across all routes and survive
  navigation without every link carrying state; this is a local dashboard, not a share-a-view app.
- *Why per-feature keys over one blob*: a feature can reset or evolve its stored shape without
  touching the others; the map "Reset filters" button just removes `localdash.map`.

### 2. A small shared persistence helper in `lib/`

A `frontend/src/lib/prefs.ts` module with two functions:

- `loadPrefs(key): unknown | null` — parse JSON, return `null` on any error (missing key, invalid
  JSON, non-object). Callers validate field-by-field: wrong-typed or unknown fields are ignored,
  never thrown on.
- `savePrefs(key, obj)` — `JSON.stringify` + `setItem`, swallowing quota/availability errors.

Each state class stays the owner of its own shape: it reads the parsed object in its constructor
(or module init), applying only fields that pass a type check, and registers persistence of its
own fields. No central registry of every preference, no versioned migration system — the tolerant
field-by-field reader *is* the migration strategy at this scale.

### 3. Allowlist semantics keyed on key-presence

For `selectedSources` and `categories`:

- Stored key absent (or unparseable) → defaults: all sources, all categories (today's behavior).
- Stored key present → `new SvelteSet(saved.filter(known))`, i.e. saved list intersected with
  currently-known source keys / category names. New sources/categories are therefore unchecked;
  removed ones are silently dropped.

The first save (triggered by any preference change) is the moment a browser opts into allowlist
mode. This was an explicit product decision over "deselected-set" storage (which would make new
sources default on): a saved preference is an explicit choice of what to see.

Consequence to accept: after opting in, checking a brand-new source shows nothing until its
categories are also checked — the FilterPanel already renders those categories as unchecked
checkboxes directly below, so the state is visible and fixable.

### 4. Persist via `$effect.root` in each state module

Each feature registers one `$effect.root(() => { $effect(() => savePrefs(KEY, snapshot())) })`
next to its singleton, where `snapshot()` reads exactly the persisted fields (spreading Sets to
arrays). Reads of the fields inside the effect give reactive tracking for free; any change to any
persisted field rewrites that feature's key wholesale.

- *Why `$effect.root`*: the singletons are created at module scope, outside component context;
  a root effect is the idiomatic Svelte 5 way to get a module-lifetime effect.
- *Why whole-object writes*: the objects are tiny (a few dozen bytes); diffing or debouncing is
  complexity with no observable benefit.
- One subtlety: the effect must not fire a save during initial load with default values before
  saved prefs are applied. Applying saved prefs synchronously in the constructor/init (before the
  effect is registered) avoids this ordering hazard entirely.

### 5. "Reset filters" clears the key and restores defaults in place

A button in the map `FilterPanel` that (a) removes `localdash.map`, (b) resets the in-memory
fields to their dynamic defaults (all sources, all categories, `showClosed=false`,
`closedWindow=60`). Because the persistence effect observes those fields, step (b) would
immediately re-save defaults — so the reset writes the default *values* but the meaningful part is
the user regains "everything on" including sources added later only until their next toggle. To
truly restore key-absent behavior, reset must suppress the follow-on save (e.g. a `skipSave` flag
consulted by the effect, cleared after the reset tick). This is the one piece of ordering care in
the design; tasks should carry a test for it.

Scope: reset ships on the map page only (it is the page with allowlist semantics where "back to
dynamic defaults" is meaningful). Events/news preferences are plain values with no
presence-dependent behavior, so reset there is just… choosing the defaults again.

## Risks / Trade-offs

- [Reset races the save effect and re-persists defaults] → explicit save-suppression around reset,
  covered by a test asserting the key is absent after reset.
- [User confusion: new source checked but map empty (categories unchecked)] → accepted per product
  decision; FilterPanel shows the unchecked categories adjacent, making it self-explanatory.
- [localStorage unavailable (private mode/embedded webview)] → helper swallows errors; app runs
  with in-memory state exactly as today.
- [Stored shape drifts as fields are added/renamed] → field-by-field tolerant reads mean old blobs
  degrade to defaults per-field; no migration code to maintain.
- [Two tabs with different toggles last-writer-wins] → accepted; single-user local dashboard,
  cross-tab sync is a non-goal.

## Open Questions

None — the allowlist-vs-default question and reset affordance were settled during exploration.
