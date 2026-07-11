// Escape for HTML built as strings (Leaflet popups); Svelte templates escape themselves.
export const esc = (s: unknown): string =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);

export const cap = (s: string): string => (s ? s[0].toUpperCase() + s.slice(1) : "");

export const fmt = (iso: string): string => {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
};
