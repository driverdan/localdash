import type { Story } from "../news";
import type { EventItem } from "../events";
import type { OutageSummary, Weather } from "./api";

// The home page owns its own slim, unfiltered state: the digest is independent
// of the news/events feature stores (which carry saved filters). Each widget
// tracks its own loaded/error flags so one failing fetch never blanks the other.
class HomeState {
  stories = $state<Story[]>([]);
  events = $state<EventItem[]>([]);
  weather = $state<Weather | null>(null);
  // null until the first successful load; an all-zero summary is real content
  // (the "no current outages" state), so error display keys off null, not zero.
  outages = $state<OutageSummary | null>(null);

  storiesLoaded = $state(false);
  eventsLoaded = $state(false);
  weatherLoaded = $state(false);
  outagesLoaded = $state(false);
  storiesError = $state(false);
  eventsError = $state(false);
  weatherError = $state(false);
  outagesError = $state(false);
}

export const home = new HomeState();
