import type { Story } from "../news";
import type { EventItem } from "../events";

// The home page owns its own slim, unfiltered state: the digest is independent
// of the news/events feature stores (which carry saved filters). Each widget
// tracks its own loaded/error flags so one failing fetch never blanks the other.
class HomeState {
  stories = $state<Story[]>([]);
  events = $state<EventItem[]>([]);

  storiesLoaded = $state(false);
  eventsLoaded = $state(false);
  storiesError = $state(false);
  eventsError = $state(false);
}

export const home = new HomeState();
