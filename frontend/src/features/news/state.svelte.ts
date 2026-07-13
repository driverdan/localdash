import { asBool, asNumber, asString, loadPrefs, persistPrefs } from "../../lib/prefs.svelte";
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
    this.tabs.some(([slug]) => slug === this.activeTab) ? this.activeTab : "all",
  );

  shownStories = $derived.by(() =>
    this.stories.filter(
      (s) =>
        (!this.multiOnly || s.source_count > 1) &&
        (this.shownTab === "all" || s.category === this.shownTab),
    ),
  );

  /** "All" view: [slug, label, stories] sections in category display order. */
  groupedShown = $derived.by(() =>
    Object.entries(this.categories)
      .map(([slug, label]): [string, string, Story[]] => [
        slug,
        label,
        this.shownStories.filter((s) => s.category === slug),
      ])
      .filter(([, , group]) => group.length > 0),
  );
}

export const news = new NewsState();

persistPrefs(PREFS_KEY, () => ({
  activeTab: news.activeTab,
  hours: news.hours,
  multiOnly: news.multiOnly,
}));
