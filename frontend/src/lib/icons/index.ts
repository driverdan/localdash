// Global icon module: one registry, two render paths. Import from here.
//   iconSvg(name, opts) -> SVG string (imperative/HTML, e.g. Leaflet divIcon)
//   Icon.svelte         -> component (Svelte templates)
export { iconSvg, type IconName, type IconOptions } from "./iconSvg";
export { ICONS } from "./registry";
export { default as Icon } from "./Icon.svelte";
