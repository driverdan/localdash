// Reconnecting WebSocket helper, feature-agnostic. Retries 3s after any close
// until the returned disposer is called.

export type ConnectionState = "connecting" | "live" | "disconnected";

export interface WsOptions {
  path: string; // e.g. /api/v1/ws (same-origin; ws/wss follows the page protocol)
  onMessage: (data: unknown) => void;
  onStatus?: (state: ConnectionState) => void;
  retryMs?: number;
}

export function connectWebSocket(opts: WsOptions): () => void {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const url = `${proto}://${location.host}${opts.path}`;
  let socket: WebSocket | null = null;
  let timer: number | undefined;
  let stopped = false;

  function open() {
    socket = new WebSocket(url);
    socket.onopen = () => opts.onStatus?.("live");
    socket.onclose = () => {
      if (stopped) return;
      opts.onStatus?.("disconnected");
      timer = window.setTimeout(open, opts.retryMs ?? 3000);
    };
    socket.onmessage = (ev) => opts.onMessage(JSON.parse(ev.data));
  }

  open();
  return () => {
    stopped = true;
    window.clearTimeout(timer);
    socket?.close();
  };
}
