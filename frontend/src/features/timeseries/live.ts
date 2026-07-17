import { onReconnect, subscribe } from "../../lib/live.svelte";
import { loadActive } from "./api";
import { ts } from "./state.svelte";
import type { DiffMessage, EntityId } from "./types";

// An incident dropped out of the feed. Keep it (muted) when "show closed" is on,
// otherwise remove it from the map entirely. The feature object is replaced, not
// mutated, so reference equality tells MapView which markers actually changed.
function closeEntity(id: EntityId): void {
  const f = ts.features.get(id);
  if (!ts.showClosed || !f) {
    ts.features.delete(id);
    return;
  }
  ts.features.set(id, {
    ...f,
    properties: {
      ...f.properties,
      active: false,
      status: "Closed",
      last_seen_at: new Date().toISOString(),
    },
  });
}

/** Subscribe to the shared bus's timeseries diffs; returns a disposer.
 *  Mount-scoped: the dashboard reloads active entities on every mount, so an
 *  off-route subscription would buy nothing. */
export function connectLive(): () => void {
  const disposeDiff = subscribe("timeseries", (raw) => {
    const msg = raw as unknown as DiffMessage;
    // Every source arrives on the bus; filter client-side by selectedSources.
    if (msg.type !== "diff" || !ts.selectedSources.has(msg.source)) return;
    for (const f of msg.new) ts.features.set(f.id, f);
    for (const f of msg.updated) ts.features.set(f.id, f);
    for (const id of msg.closed) closeEntity(id);
  });
  // Diffs broadcast while disconnected are gone; reload the world instead.
  const disposeReconnect = onReconnect(() => void loadActive());
  return () => {
    disposeDiff();
    disposeReconnect();
  };
}
