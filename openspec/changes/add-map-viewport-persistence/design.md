## Context

`MapView.svelte` builds the Leaflet map imperatively in `onMount` with a hardcoded
`DEFAULT_VIEW` (center = Chattanooga, zoom = 11). It already mirrors the live viewport out on
`moveend` / `zoomend` via `publishViewport()` — currently only to the shell debug store
(`debug.setMapViewport`). No viewport state is persisted, so every reload discards the user's
position.

The frontend already has a tolerant localStorage layer in `lib/prefs.svelte.ts`
(`loadPrefs` / `savePrefs`, `asNumber` finite-check, swallowed write failures). The timeseries
feature persists a filter blob under `localdash.map` via `persistPrefs`, whose reactive
persist-on-change effect deliberately makes **key-presence meaningful**: once written, the saved
`categories` list switches filtering from all-on default into allowlist mode.

## Goals / Non-Goals

**Goals:**
- Default zoom becomes 12.
- The map restores its last `{ zoom, lat, lng }` on load and saves it as the user pans/zooms.
- Restoration is robust: corrupt/partial storage never breaks page load and never yields a
  half-restored view.

**Non-Goals:**
- No server-side or per-account persistence (per-browser only, consistent with existing prefs).
- No change to `flyTo` (table click → zoom 15) or detail-track rendering.
- No change to the existing debug-store viewport publish.
- No unification of the debug-store viewport and the persisted viewport into one mechanism.

## Decisions

**1. Separate key `localdash.map.view`, not the `localdash.map` filter blob.**
Viewport is high-frequency and always wants to save; the filter blob is low-frequency and uses
key-absence as an allowlist signal. Folding viewport into `localdash.map` would mean a single pan
serializes the current `categories`, silently flipping filtering into allowlist mode (sources added
later would start unchecked). A dedicated key keeps the two concerns independent.
*Alternative considered:* nesting a `view` field inside the `localdash.map` blob — rejected because
`persistPrefs` overwrites the whole blob and would clobber a field it doesn't know about (and vice
versa), a read-modify-write race between two writers on one key.

**2. Imperative save/load in `MapView.svelte`, reusing `prefs.svelte.ts` primitives, not
`persistPrefs`.**
The Leaflet map is imperative and lives outside the `ts` reactive state; `publishViewport()` is
already the single choke point on `moveend` / `zoomend`. Saving there (a `savePrefs` call beside the
existing `debug.setMapViewport`) is the smallest, most local change and sidesteps
`persistPrefs`'s allowlist-oriented "first run writes nothing" behavior, which viewport does not
want. `loadPrefs` + `asNumber` give the tolerant read for free.
*Alternative considered:* lifting viewport into `TimeseriesState` and using `persistPrefs` — more
plumbing for state that is inherently imperative, and re-introduces the allowlist concern.

**3. All-or-nothing restore.**
Read all three fields with `asNumber`; if any is `null` (missing / non-finite), ignore the stored
value entirely and use `DEFAULT_VIEW`. A partially valid record (e.g. good zoom, bad lat) is treated
as no record, avoiding a nonsensical center-with-wrong-zoom view. Leaflet additionally clamps a
restored zoom to `maxZoom` (18), so out-of-range zoom is self-correcting.

## Risks / Trade-offs

- **Two writers emit viewport on every move (debug store + localStorage).** → Both fire only on
  `moveend` / `zoomend` (once per gesture, not continuously) and are cheap; the write is wrapped by
  `savePrefs`'s swallow-on-failure. Negligible cost.
- **Spec invariant "one JSON key per feature" is relaxed.** → Documented explicitly in the
  `frontend-preferences` delta as a namespaced view-state key written independently of the main blob;
  the collision this avoids is the reason for the exception.
- **A user with a saved far-away viewport won't see the new zoom-12 default.** → Intended: their saved
  position wins. The default only applies to first-time / cleared storage.
