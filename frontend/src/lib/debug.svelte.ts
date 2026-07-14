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

class DebugState {
  /** Modal visibility, toggled by the π button. */
  open = $state(false);
  /** Live map viewport, or null when the map isn't mounted (off the `/map` route). */
  map = $state<MapViewport | null>(null);

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
}

export const debug = new DebugState();
