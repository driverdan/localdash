// Singleton live-update bus: the app's one WebSocket to /api/v1/ws.
//
// Every server message carries a `topic`; features subscribe by topic and the
// bus dispatches. Timeseries messages carry diff payloads; news/events/weather
// are payload-free invalidation pings whose handlers refetch over REST. The
// shell starts the connection once; there is no per-feature socket.

import { connectWebSocket, type ConnectionState } from "./ws";

/** Envelope of every bus message; topic-specific fields ride along untyped. */
export interface LiveMessage {
  topic: string;
  type: string;
  [key: string]: unknown;
}

type Handler = (msg: LiveMessage) => void;

const handlers = new Map<string, Set<Handler>>();
const reconnectHandlers = new Set<() => void>();

let state = $state<ConnectionState>("connecting");
let started = false;
let everLive = false;

/** Open the app-lifetime connection. Idempotent; the shell calls it once. */
export function startLive(): void {
  if (started) return;
  started = true;
  connectWebSocket({
    path: "/api/v1/ws",
    onStatus: (s) => {
      // Reconnect handlers fire only on re-connects: the boot-time first
      // "live" must not duplicate the features' on-mount initial loads.
      if (s === "live" && everLive) for (const h of [...reconnectHandlers]) h();
      if (s === "live") everLive = true;
      state = s;
    },
    onMessage: (raw) => {
      const msg = raw as LiveMessage;
      const subs = handlers.get(msg?.topic);
      // Unknown topics (future features) are dropped without error.
      if (subs) for (const h of [...subs]) h(msg);
    },
  });
}

/** Shared connection state for status indicators; features own no socket state. */
export const liveState = (): ConnectionState => state;

/** Register a handler for one topic's messages; returns a disposer. */
export function subscribe(topic: string, handler: Handler): () => void {
  let subs = handlers.get(topic);
  if (!subs) handlers.set(topic, (subs = new Set()));
  subs.add(handler);
  return () => subs.delete(handler);
}

/** Run a handler after each re-connect (missed messages are gone — refetch). */
export function onReconnect(handler: () => void): () => void {
  reconnectHandlers.add(handler);
  return () => reconnectHandlers.delete(handler);
}
