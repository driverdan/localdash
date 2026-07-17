import { onReconnect, subscribe } from "../../lib/live.svelte";
import { loadSources, loadStories } from "./api";

let registered = false;

/** Permanent bus subscription, registered once from the shell: a completed
 *  server news cycle (or a reconnect, whose pings were missed) refetches
 *  stories and sources into the singleton store — current `hours` applies —
 *  so the feed is fresh even while another route is visible. */
export function registerLive(): void {
  if (registered) return;
  registered = true;
  const reload = () => {
    loadStories();
    loadSources();
  };
  subscribe("news", reload);
  onReconnect(reload);
}
