import {
  asBool,
  asNumber,
  asString,
  loadPrefs,
  persistPrefs,
} from "../../lib/prefs.svelte";
import type { FeedHealth, Story } from "./types";

const PREFS_KEY = "localdash.news";

// The feature's reactive state: raw API responses are $state; the tab list and
// visible/grouped story sets are $derived (mirrors the timeseries store style).
class NewsState {
  stories = $state<Story[]>([]);
  /** category slug -> label, in display order (from the stories response). */
  categories = $state<Record<string, string>>({});
  sources = $state<FeedHealth[]>([]);

  activeTab = $state("all");
  hours = $state(72);
  multiOnly = $state(false);

  // Saved preferences apply here, before the persist effect below is registered.
  constructor() {
    const saved = loadPrefs(PREFS_KEY);
    if (!saved) return;
    this.activeTab = asString(saved.activeTab) ?? this.activeTab;
    this.hours = asNumber(saved.hours) ?? this.hours;
    this.multiOnly = asBool(saved.multiOnly) ?? this.multiOnly;
  }

  loadError = $state(false);
  refreshing = $state(false);
  statusText = $state("");

  /** "all" plus each category that has stories, in display order. */
  tabs = $derived.by(() => {
    const present = new Set(this.stories.map((s) => s.category));
    return [
      ["all", "All"] as [string, string],
      ...Object.entries(this.categories).filter(([slug]) => present.has(slug)),
    ];
  });

  /**
   * The tab the feed actually renders: activeTab when it's among the available
   * tabs, else "all". Covers a restored tab whose category has no stories (and
   * the window before stories load) without overwriting the saved preference.
   */
  shownTab = $derived.by(() =>
    this.tabs.some(([slug]) => slug === this.activeTab)
      ? this.activeTab
      : "all",
  );

  shownStories = $derived.by(() =>
    this.stories.filter(
      (s) =>
        (!this.multiOnly || s.source_count > 1) &&
        (this.shownTab === "all" || s.category === this.shownTab),
    ),
  );

  /** Label of the shown tab, for the feed's single section heading. */
  shownTabLabel = $derived.by(
    () =>
      this.tabs.find(([slug]) => slug === this.shownTab)?.[1] ??
      this.tabs[0][1],
  );
}

export const news = new NewsState();

/**
 * Set the shared category slug->label map that `StoryCard` reads for badge
 * labels. The map is server-defined (not a user preference), so the home
 * feature can feed it from its own stories response and a later `/news` visit
 * simply overwrites it with an identical value — no filter leakage.
 */
export function setCategoryLabels(map: Record<string, string>): void {
  news.categories = map;
}

persistPrefs(PREFS_KEY, () => ({
  activeTab: news.activeTab,
  hours: news.hours,
  multiOnly: news.multiOnly,
}));
