import type { FeedHealth, Story } from "./types";

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

  shownStories = $derived.by(() =>
    this.stories.filter(
      (s) =>
        (!this.multiOnly || s.source_count > 1) &&
        (this.activeTab === "all" || s.category === this.activeTab),
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
