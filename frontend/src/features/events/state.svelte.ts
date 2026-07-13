import { asNumber, asStringArray, loadPrefs, persistPrefs } from "../../lib/prefs.svelte";
import type { EventItem } from "./types";

const PREFS_KEY = "localdash.events";

// The feature's reactive state. Filters map 1:1 to /items query params —
// changing one refetches server-side (no client-side filtering of a cached
// superset), so `items` is always exactly what the current filters match.
class EventsState {
  items = $state<EventItem[]>([]);
  /** All known topic tags (chips), from /api/v1/events/tags. */
  tags = $state<string[]>([]);

  /** Active filters. Topics and maxMiles persist; search is ephemeral. */
  topics = $state<string[]>([]);
  maxMiles = $state<number | null>(null);
  search = $state("");

  // Saved preferences apply here, before the persist effect below is registered.
  // Saved topics are trusted as-is for the initial fetch and intersected with
  // the live tag list once it arrives (see loadTags).
  constructor() {
    const saved = loadPrefs(PREFS_KEY);
    if (!saved) return;
    this.topics = asStringArray(saved.topics) ?? this.topics;
    const miles = asNumber(saved.maxMiles);
    if (miles !== null) this.maxMiles = miles;
  }

  loadError = $state(false);
  refreshing = $state(false);
  statusText = $state("");

  toggleTopic(name: string) {
    this.topics = this.topics.includes(name)
      ? this.topics.filter((t) => t !== name)
      : [...this.topics, name];
  }
}

export const events = new EventsState();

persistPrefs(PREFS_KEY, () => ({
  topics: [...events.topics],
  maxMiles: events.maxMiles,
}));
