# Tasks: persist-client-preferences

## 1. Shared persistence helper

- [x] 1.1 Create `frontend/src/lib/prefs.ts` with `loadPrefs(key)` (parse JSON from localStorage;
      return `null` for missing key, invalid JSON, or non-object; never throw) and
      `savePrefs(key, obj)` (stringify + setItem, swallowing storage errors), plus a
      `removePrefs(key)` for reset

## 2. Map (timeseries) preferences

- [x] 2.1 In `timeseries/state.svelte.ts`, initialize `selectedSources` and `categories` from
      `localdash.map` when present — saved arrays type-checked and intersected with known source
      keys / category names — otherwise all-on defaults; apply `showClosed`/`closedWindow` from
      saved prefs field-by-field with type checks
- [x] 2.2 Register a module-scope `$effect.root` that saves `{selectedSources, categories,
      showClosed, closedWindow}` to `localdash.map` whenever any of them changes (Sets spread to
      arrays), applied after initial load so startup never writes defaults
- [x] 2.3 Add a `resetFilters()` action that removes `localdash.map`, restores all-on defaults and
      `showClosed=false`/`closedWindow=60`, and suppresses the save effect for that change so the
      key stays absent afterward
- [x] 2.4 Add a "Reset filters" button to `FilterPanel.svelte` wired to `resetFilters()`, styled
      consistently with the existing panel controls

## 3. Events preferences

- [x] 3.1 In `events/state.svelte.ts`, initialize `topics` and `maxMiles` from `localdash.events`
      with per-field type checks (search stays ephemeral), intersect saved topics with available
      tags once tags load, and persist both fields on change via a module-scope effect; confirm the
      initial items fetch carries the restored filters

## 4. News preferences

- [x] 4.1 In `news/state.svelte.ts`, initialize `activeTab`, `hours`, and `multiOnly` from
      `localdash.news` with per-field type checks and persist them on change via a module-scope
      effect; confirm the initial story fetch uses the restored `hours`
- [x] 4.2 Make the feed render the "All" view when the saved `activeTab` is not among the available
      tabs after stories load

## 5. Verification

- [x] 5.1 Run `npm run check` in `frontend/` and rebuild via
      `sg docker -c 'docker compose up --build -d'`
- [x] 5.2 Verify in the browser: toggle map sources/categories/show-closed, events topics/distance,
      news tab/window/multi-only; reload after each and confirm restoration; confirm search boxes
      reset on reload
- [x] 5.3 Verify allowlist + reset semantics: with saved prefs, `localdash.map` lists only checked
      items; after "Reset filters" the key is absent from localStorage (not re-saved with defaults)
      and everything is checked; corrupt each key by hand and confirm the page loads with defaults
