import { connectWebSocket } from "../../lib/ws";
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

/** Subscribe to the live diff stream; returns a disposer. */
export function connectLive(): () => void {
  return connectWebSocket({
    // No source filter: subscribe to every source and filter client-side by selectedSources.
    path: "/api/v1/timeseries/ws",
    onStatus: (state) => (ts.connection = state),
    onMessage: (raw) => {
      const msg = raw as DiffMessage;
      if (msg.type !== "diff" || !ts.selectedSources.has(msg.source)) return; // ignore muted sources
      for (const f of msg.new) ts.features.set(f.id, f);
      for (const f of msg.updated) ts.features.set(f.id, f);
      for (const id of msg.closed) closeEntity(id);
    },
  });
}
