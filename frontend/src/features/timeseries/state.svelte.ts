import { SvelteMap, SvelteSet } from "svelte/reactivity";
import { asBool, asNumber, asStringArray, loadPrefs, persistPrefs } from "../../lib/prefs.svelte";
import type { ConnectionState } from "../../lib/ws";
import { SOURCES, cfgFor, isClosed } from "./sources";
import type { EntityId, TrackedFeature, TrackPoint } from "./types";

const PREFS_KEY = "localdash.map";

const allSourceKeys = (): string[] => Object.keys(SOURCES);
const allCategories = (): string[] => [
  ...new Set(Object.values(SOURCES).flatMap((s) => s.categories)),
];

// The feature's reactive state. Raw inputs are $state; everything the old app
// maintained by hand (visible set, dropdown options, category union) is $derived,
// so there is no refreshAll()/reconcileSelect() call-graph to keep in sync.
class TimeseriesState {
  /** entity id -> GeoJSON feature. Values are replaced (never mutated) on update. */
  features = new SvelteMap<EntityId, TrackedFeature>();

  selectedSources = new SvelteSet<string>(allSourceKeys());
  /** Enabled categories; defaults to every category of every selected source. */
  categories = new SvelteSet<string>(allCategories());
  status = $state("");
  jurisdiction = $state("");
  search = $state("");
  showClosed = $state(false);
  closedWindow = $state(60);

  connection = $state<ConnectionState>("connecting");
  /** Entity whose detail panel is open, if any. */
  detailId = $state<EntityId | null>(null);
  /** Track of the open detail entity, drawn on the map by MapView. */
  detailTrack = $state<TrackPoint[] | null>(null);
  /** One-shot map focus request (set by the table, consumed by MapView). */
  flyToRequest = $state<{ lat: number; lon: number } | null>(null);

  // Saved preferences apply synchronously here, before the persist effect below
  // is registered, so startup never writes a key. A saved list is an explicit
  // allowlist: it replaces the all-on default, intersected with currently-known
  // keys (stale entries dropped, sources/categories added later start unchecked).
  constructor() {
    const saved = loadPrefs(PREFS_KEY);
    if (!saved) return;
    const sources = asStringArray(saved.sources);
    if (sources) {
      this.selectedSources.clear();
      for (const k of sources) if (k in SOURCES) this.selectedSources.add(k);
    }
    const cats = asStringArray(saved.categories);
    if (cats) {
      const known = new Set(allCategories());
      this.categories.clear();
      for (const c of cats) if (known.has(c)) this.categories.add(c);
    }
    this.showClosed = asBool(saved.showClosed) ?? this.showClosed;
    this.closedWindow = asNumber(saved.closedWindow) ?? this.closedWindow;
  }

  /**
   * Back to dynamic defaults: everything on, closed hidden, and the stored key
   * deleted (not re-saved), so future sources default to checked again.
   * Callers that had showClosed on must refetch (see FilterPanel).
   */
  resetFilters(): void {
    persister.resetTo(() => {
      this.selectedSources.clear();
      for (const k of allSourceKeys()) this.selectedSources.add(k);
      this.categories.clear();
      for (const c of allCategories()) this.categories.add(c);
      this.showClosed = false;
      this.closedWindow = 60;
    });
  }

  /** Categories across the currently-selected sources, de-duped by name. */
  selectedCategoryList = $derived.by(() => {
    const out: string[] = [];
    for (const key of this.selectedSources) {
      for (const c of cfgFor(key).categories) if (!out.includes(c)) out.push(c);
    }
    return out;
  });

  visibleFeatures = $derived.by(() =>
    [...this.features.values()].filter((f) => this.passesFilters(f)),
  );

  /** Table order: most recently seen first. */
  visibleSorted = $derived.by(() =>
    [...this.visibleFeatures].sort((a, b) =>
      String(b.properties.last_seen_at ?? "").localeCompare(String(a.properties.last_seen_at ?? "")),
    ),
  );

  statusOptions = $derived.by(() => this.uniq((f) => String(f.properties.status ?? "")));
  jurisdictionOptions = $derived.by(() =>
    this.uniq((f) => cfgFor(f.properties.source).jurisdiction(f.properties)),
  );

  passesFilters(f: TrackedFeature): boolean {
    const p = f.properties;
    if (!this.selectedSources.has(p.source)) return false;
    if (isClosed(f) && !this.showClosed) return false;
    if (!this.categories.has(p.category)) return false;
    if (this.status && p.status !== this.status) return false;
    const cfg = cfgFor(p.source);
    if (this.jurisdiction && cfg.jurisdiction(p) !== this.jurisdiction) return false;
    if (this.search) {
      const hay = `${cfg.title(p)} ${cfg.location(p)} ${p.status || ""}`.toLowerCase();
      if (!hay.includes(this.search.toLowerCase())) return false;
    }
    return true;
  }

  /** Color for a category checkbox/dot (from whichever selected source defines it). */
  catColor(cat: string): string {
    for (const key of this.selectedSources) {
      const c = cfgFor(key).colors[cat];
      if (c) return c;
    }
    return "#6b7280";
  }

  private uniq(getter: (f: TrackedFeature) => string): string[] {
    const vals = [...this.features.values()]
      .filter((f) => this.selectedSources.has(f.properties.source))
      .map(getter)
      .filter(Boolean);
    return [...new Set(vals)].sort();
  }
}

export const ts = new TimeseriesState();

const persister = persistPrefs(PREFS_KEY, () => ({
  sources: [...ts.selectedSources],
  categories: [...ts.categories],
  showClosed: ts.showClosed,
  closedWindow: ts.closedWindow,
}));

/** Read-only view of the live-connection state, for the app shell's status bar. */
export const connectionState = (): ConnectionState => ts.connection;
