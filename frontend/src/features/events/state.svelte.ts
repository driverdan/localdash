import type { EventItem } from "./types";

// The feature's reactive state. Filters map 1:1 to /items query params —
// changing one refetches server-side (no client-side filtering of a cached
// superset), so `items` is always exactly what the current filters match.
class EventsState {
  items = $state<EventItem[]>([]);
  /** All known topic tags (chips), from /api/v1/events/tags. */
  tags = $state<string[]>([]);

  /** Active filters. */
  topics = $state<string[]>([]);
  maxMiles = $state<number | null>(null);
  search = $state("");

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
