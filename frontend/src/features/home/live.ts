import { onReconnect, subscribe } from "../../lib/live.svelte";
import { loadEvents, loadOutages, loadStories, loadWeather } from "./api";

let registered = false;

/** Permanent bus subscriptions, registered once from the shell: each widget
 *  follows its own feature's ping (and all refetch on reconnect), so the
 *  landing page stays current without polling or remounting. */
export function registerLive(): void {
  if (registered) return;
  registered = true;
  subscribe("news", () => void loadStories());
  subscribe("events", () => void loadEvents());
  subscribe("weather", () => void loadWeather());
  // Timeseries diffs carry their source; only epb ones affect the outages
  // digest (the diff payload itself is the map's concern — we just refetch).
  subscribe("timeseries", (msg) => {
    if (msg.source === "epb") void loadOutages();
  });
  onReconnect(() => {
    loadStories();
    loadEvents();
    loadWeather();
    loadOutages();
  });
}
