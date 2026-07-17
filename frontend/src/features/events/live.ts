import { onReconnect, subscribe } from "../../lib/live.svelte";
import { loadItems, loadTags } from "./api";

let registered = false;

/** Permanent bus subscription, registered once from the shell: an events
 *  cycle that changed data (or a reconnect, whose pings were missed) refetches
 *  items — active topic/distance/search filters apply via itemsURL — and tags
 *  into the singleton store, so the page is fresh even while another route is
 *  visible. */
export function registerLive(): void {
  if (registered) return;
  registered = true;
  const reload = () => {
    loadItems();
    loadTags();
  };
  subscribe("events", reload);
  onReconnect(reload);
}
