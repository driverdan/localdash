import { onReconnect, subscribe } from "../../lib/live.svelte";
import { loadEvents, loadStories, loadWeather } from "./api";

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
  onReconnect(() => {
    loadStories();
    loadEvents();
    loadWeather();
  });
}
