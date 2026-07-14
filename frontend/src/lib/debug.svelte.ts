// Shell-owned debug overlay state. Lives in `lib/` (shell code) so any feature may
// WRITE to it and the shell debug panel may READ it without a cross-feature import
// — the frontend-shell isolation rule forbids feature→feature imports but allows
// feature→lib and shell→lib.
//
// General by design: `open` drives the modal; per-area slices (starting with the
// map viewport) hold whatever runtime state a route wants to expose. A new debug
// section is one slice here plus one block in DebugPanel — existing ones untouched.

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
  /** Modal visibility, toggled by the π button. */
  open = $state(false);
  /** Live map viewport, or null when the map isn't mounted (off the `/map` route). */
  map = $state<MapViewport | null>(null);
  /**
   * Feature-registered actions. Only the mounted feature's action is present, so
   * the panel is route-aware for free. Features write here on mount and remove on
   * teardown, mirroring the map-viewport slice.
   */
  actions = $state<DebugAction[]>([]);

  toggle(): void {
    this.open = !this.open;
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
