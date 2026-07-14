// The one place icons are registered. Each entry imports a single Lucide icon by
// name, so the bundler tree-shakes away every icon we don't list here. Add a glyph
// = add one import + one row. Keys are Lucide's canonical kebab-case names, giving
// callers a stable string API (`iconSvg("siren")`) decoupled from the imports.
import {
  Siren,
  Flame,
  Ambulance,
  CircleQuestionMark,
  TriangleAlert,
  TrafficCone,
  PartyPopper,
  OctagonAlert,
  Zap,
  Cable,
  MapPin,
  type IconNode,
} from "lucide";

export const ICONS = {
  siren: Siren,
  flame: Flame,
  ambulance: Ambulance,
  "circle-question-mark": CircleQuestionMark,
  "triangle-alert": TriangleAlert,
  "traffic-cone": TrafficCone,
  "party-popper": PartyPopper,
  "octagon-alert": OctagonAlert,
  zap: Zap,
  cable: Cable,
  "map-pin": MapPin,
} satisfies Record<string, IconNode>;

export type IconName = keyof typeof ICONS;
