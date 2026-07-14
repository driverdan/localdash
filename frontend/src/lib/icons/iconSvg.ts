// Turn a registered icon into a standalone SVG string. This is the primitive both
// render paths share: imperative/HTML callers (e.g. Leaflet `divIcon`) use it
// directly, and `Icon.svelte` renders its output via {@html}. Lucide icons stroke
// with `currentColor`, so `color` simply sets the stroke.
import { ICONS, type IconName } from "./registry";

export type { IconName } from "./registry";

export interface IconOptions {
  /** Width/height in px (icons are square). Default 24. */
  size?: number;
  /** Stroke color. Default "currentColor" so CSS `color` tints it. */
  color?: string;
  /** Stroke width in the 24×24 viewBox. Default 2. */
  strokeWidth?: number;
  /** Extra class on the root <svg>. */
  class?: string;
}

const attrs = (a: Record<string, unknown>): string =>
  Object.entries(a)
    .filter(([, v]) => v != null)
    .map(([k, v]) => `${k}="${v}"`)
    .join(" ");

export function iconSvg(name: IconName, opts: IconOptions = {}): string {
  const { size = 24, color = "currentColor", strokeWidth = 2 } = opts;
  const children = ICONS[name]
    .map(([tag, a]) => `<${tag} ${attrs(a)} />`)
    .join("");
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" ` +
    `viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="${strokeWidth}" ` +
    `stroke-linecap="round" stroke-linejoin="round"` +
    (opts.class ? ` class="${opts.class}"` : "") +
    `>${children}</svg>`
  );
}
