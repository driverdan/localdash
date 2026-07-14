import { SvelteMap, SvelteSet } from "svelte/reactivity";
import {
  asBool,
  asNumber,
  asStringArray,
  loadPrefs,
  persistPrefs,
} from "../../lib/prefs.svelte";
import type { ConnectionState } from "../../lib/ws";
import { SOURCES, catKey, cfgFor, isClosed } from "./sources";
import type { EntityId, TrackedFeature, TrackPoint } from "./types";

const PREFS_KEY = "localdash.map";

// Source-scoped category keys ("source:category") for every category of every
// source; unique by construction, so no de-duplication is needed.
const allCategoryKeys = (): string[] =>
  Object.entries(SOURCES).flatMap(([key, s]) =>
    s.categories.map((c) => catKey(key, c)),
  );

// The feature's reactive state. Raw inputs are $state; everything the old app
// maintained by hand (visible set, dropdown options, category union) is $derived,
// so there is no refreshAll()/reconcileSelect() call-graph to keep in sync.
class TimeseriesState {
  /** entity id -> GeoJSON feature. Values are replaced (never mutated) on update. */
  features = new SvelteMap<EntityId, TrackedFeature>();

  /**
   * The single source of truth for source/category filtering: the set of enabled
   * source-scoped category keys ("source:category"). A source is "loaded" iff at
   * least one of its categories is enabled (see `selectedSources`), so there is no
   * separate source-selection state.
   */
  categories = new SvelteSet<string>(allCategoryKeys());
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
  /** One-shot map focus request: the entity id to focus (set by the table,
   *  consumed by MapView, which flies to a point or fits a polygon's bounds). */
  flyToRequest = $state<EntityId | null>(null);

  // Saved preferences apply synchronously here, before the persist effect below
  // is registered, so startup never writes a key. A saved list is an explicit
  // allowlist: it replaces the all-on default, intersected with currently-known
  // category keys (stale entries dropped, categories added later start unchecked).
  constructor() {
    const saved = loadPrefs(PREFS_KEY);
    if (!saved) return;
    const cats = asStringArray(saved.categories);
    if (cats) {
      const known = new Set(allCategoryKeys());
      this.categories.clear();
      // Stale keys — including pre-scoping bare category names — are dropped.
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
      this.categories.clear();
      for (const c of allCategoryKeys()) this.categories.add(c);
      this.showClosed = false;
      this.closedWindow = 60;
    });
  }

  /**
   * Loaded sources, derived from the category selection: a source is on iff at
   * least one of its categories is enabled. Drives what `loadActive` fetches and
   * which push diffs `live.ts` accepts.
   */
  selectedSources = $derived.by(() => {
    const out = new Set<string>();
    for (const [key, s] of Object.entries(SOURCES)) {
      if (s.categories.some((c) => this.categories.has(catKey(key, c))))
        out.add(key);
    }
    return out;
  });

  visibleFeatures = $derived.by(() =>
    [...this.features.values()].filter((f) => this.passesFilters(f)),
  );

  /** Table order: most recently seen first. */
  visibleSorted = $derived.by(() =>
    [...this.visibleFeatures].sort((a, b) =>
      String(b.properties.last_seen_at ?? "").localeCompare(
        String(a.properties.last_seen_at ?? ""),
      ),
    ),
  );

  statusOptions = $derived.by(() =>
    this.uniq((f) => String(f.properties.status ?? "")),
  );
  jurisdictionOptions = $derived.by(() =>
    this.uniq((f) => cfgFor(f.properties.source).jurisdiction(f.properties)),
  );

  passesFilters(f: TrackedFeature): boolean {
    const p = f.properties;
    // A scoped-category miss also excludes features of any source whose
    // categories are all off, so no separate source-membership check is needed.
    if (!this.categories.has(catKey(p.source, p.category))) return false;
    if (isClosed(f) && !this.showClosed) return false;
    if (this.status && p.status !== this.status) return false;
    const cfg = cfgFor(p.source);
    if (this.jurisdiction && cfg.jurisdiction(p) !== this.jurisdiction)
      return false;
    if (this.search) {
      const hay =
        `${cfg.title(p)} ${cfg.location(p)} ${p.status || ""}`.toLowerCase();
      if (!hay.includes(this.search.toLowerCase())) return false;
    }
    return true;
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
  // `sources` is derived from `categories`, so only the scoped category keys are
  // persisted (plus the closed-window preferences).
  categories: [...ts.categories],
  showClosed: ts.showClosed,
  closedWindow: ts.closedWindow,
}));

/** Read-only view of the live-connection state, for the app shell's status bar. */
export const connectionState = (): ConnectionState => ts.connection;
