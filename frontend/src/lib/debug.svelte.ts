// Shell-owned debug overlay state. Lives in `lib/` (shell code) so any feature may
// WRITE to it and the shell debug panel may READ it without a cross-feature import
// — the frontend-shell isolation rule forbids feature→feature imports but allows
// feature→lib and shell→lib.
//
// General by design: `open` drives the modal; per-area slices (starting with the
// map viewport) hold whatever runtime state a route wants to expose. A new debug
// section is one slice here plus one block in DebugPanel — existing ones untouched.
import { listPrefs, removePrefs, type StoredPref } from "./prefs.svelte";

/** The map's live viewport, mirrored out of Leaflet by MapView. */
export interface MapViewport {
  zoom: number;
  lat: number;
  lng: number;
}

// A feature-provided debug action, rendered by DebugPanel as a button + status
// line. `disabled` and `status` are getters (not snapshots) so the panel reflects
// live feature state — e.g. a button that greys out and a status that ticks over
// during an in-flight refresh — without `lib/` importing any feature code.
export interface DebugAction {
  /** Stable key, e.g. "news-refresh". */
  id: string;
  /** Button text, e.g. "Refresh feeds". */
  label: string;
  /** Invoked when the button is clicked. */
  run: () => void;
  /** Whether the button is disabled (read live). */
  readonly disabled: boolean;
  /** Status text; empty string hides the status line. */
  readonly status: string;
}

class DebugState {
  #open = $state(false);

  /** Modal visibility, toggled by the π button. */
  get open(): boolean {
    return this.#open;
  }

  /** Opening re-reads the settings snapshot, whatever path opened the modal. */
  set open(value: boolean) {
    if (value === this.#open) return;
    this.#open = value;
    if (value) this.refreshSettings();
  }

  /** Live map viewport, or null when the map isn't mounted (off the `/map` route). */
  map = $state<MapViewport | null>(null);
  /**
   * Feature-registered actions. Only the mounted feature's action is present, so
   * the panel is route-aware for free. Features write here on mount and remove on
   * teardown, mirroring the map-viewport slice.
   */
  actions = $state<DebugAction[]>([]);
  /**
   * Stored `localdash.*` preference keys — a snapshot taken when the modal
   * opens, not a live view. Same-tab writes fire no `storage` event (it notifies
   * other tabs only), so a key the app rewrites — a map pan restoring
   * `localdash.map.view` — can't be observed while the panel is open. Re-reading
   * on open is what surfaces it, and is why a resurrected key shows up again on
   * reopen with no notice: the delete really was undone.
   *
   * Enumerated rather than registered, so a key a future feature adds is listed
   * with no registration step, and no feature module is imported here.
   */
  settings = $state<StoredPref[]>([]);
  /** Keys deleted since the modal opened; their rows stay listed, but flagged. */
  deletedSettings = $state<Set<string>>(new Set());

  toggle(): void {
    this.open = !this.open;
  }

  refreshSettings(): void {
    this.settings = listPrefs();
    this.deletedSettings = new Set();
  }

  /**
   * Delete one stored key. Deliberately does NOT reload or reset the owning
   * feature's in-memory state, so nothing visibly changes and that feature's
   * next persisted-field change rewrites its blob, restoring the key with the
   * pre-delete values. The row stays listed and flagged so the panel can say the
   * delete only lands on reload.
   */
  deleteSetting(key: string): void {
    removePrefs(key);
    this.deletedSettings = new Set(this.deletedSettings).add(key);
  }

  setMapViewport(v: MapViewport): void {
    this.map = v;
  }

  /** Cleared on MapView teardown so a stale viewport isn't shown after leaving `/map`. */
  clearMapViewport(): void {
    this.map = null;
  }

  /** Register (or replace, by id) a feature debug action. */
  registerAction(action: DebugAction): void {
    this.actions = [...this.actions.filter((a) => a.id !== action.id), action];
  }

  /** Remove a feature debug action by id; idempotent. */
  unregisterAction(id: string): void {
    this.actions = this.actions.filter((a) => a.id !== id);
  }
}

export const debug = new DebugState();
