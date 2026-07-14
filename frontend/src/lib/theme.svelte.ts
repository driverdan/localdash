// Theme registry — the single place a theme is defined. Adding a theme is one
// entry here plus a matching `[data-theme="<id>"]` stylesheet; no feature code
// changes. Each theme's CSS is free to restyle layout, typography, and color by
// targeting the frontend-styling semantic hooks, not just swap colors.
//
// Theme is a preference, but unlike lib/prefs it must apply BEFORE first paint
// (a post-mount apply flashes the default theme first). So the source of truth
// at load time is the synchronous inline bootstrap in index.html, which reads
// the same `localdash.theme` key this module writes. This module owns the
// reactive selection for the switcher UI and the apply/persist write path.

export interface Theme {
  id: string;
  label: string;
  // Optional basemap override. A dark theme ships its own dark tile layer so the
  // map doesn't stay bright under a dark shell. Absent → MapView uses the
  // server-configured tile_url (the default theme's basemap).
  tileUrl?: string;
  tileAttribution?: string;
}

// Shared contract with the index.html bootstrap script — keep the literal in sync.
const STORAGE_KEY = "localdash.theme";

// The current appearance is the default theme; it needs no `[data-theme]`
// stylesheet (base + feature sheets are the default styling). "dark" ships as
// proof the contract supports layout/type changes, not only color.
export const themes: Theme[] = [
  { id: "light", label: "Light" },
  {
    id: "dark",
    label: "Dark",
    tileUrl: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
    tileAttribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
  },
];

const DEFAULT_ID = themes[0].id;

function readStored(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) ?? DEFAULT_ID;
  } catch {
    return DEFAULT_ID;
  }
}

// Reactive current selection, for the switcher. Initialised from the stored
// value the inline bootstrap already applied to the document root (falling back
// to the default when absent or storage is unavailable).
let current = $state(readStored());

export function currentTheme(): string {
  return current;
}

// The active theme's registry entry (default theme when the id is unknown), so
// callers like MapView can read its basemap override.
export function activeTheme(): Theme {
  return themes.find((t) => t.id === current) ?? themes[0];
}

// Apply a theme: update the reactive selection, set `data-theme` on the document
// root (the inline bootstrap does the same at load), and persist under the key
// the bootstrap reads. An unknown id still writes through — CSS falls through to
// the default styling for an unmatched `[data-theme]`, so nothing breaks.
export function applyTheme(id: string): void {
  current = id;
  document.documentElement.dataset.theme = id;
  try {
    localStorage.setItem(STORAGE_KEY, id);
  } catch {
    /* storage unavailable — theme still applies in-memory for this session */
  }
}
