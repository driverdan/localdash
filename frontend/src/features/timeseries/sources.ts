import { cap } from "../../lib/format";
import type { SourceConfig, TrackedFeature, TrackedProperties } from "./types";

const str = (v: unknown): string => (v == null ? "" : String(v));

// EPB outage status -> marker color, matching epb.com/outage-storm-center's map.
export const EPB_STATUS_COLORS: Record<string, string> = {
  OUTAGE_REPORTED: "#E10101", // Outage Reported (red)
  EN_ROUTE: "#F97B06", // Crew En Route (orange)
  REPAIR_IN_PROGRESS: "#0392CF", // Repair in Progress (blue)
  RESTORED: "#76A84F", // Restored (green)
  Closed: "#76A84F", // dropped from the feed == service restored
};

// EPB scales each marker by customers affected (16 + n*0.024, bucketed), like its map.
function epbMarkerSize(p: TrackedProperties): number {
  const n = Number(p.customer_quantity);
  const s = 16 + (Number.isFinite(n) ? n * 0.024 : 0);
  return s >= 40 ? 40 : s >= 32 ? 32 : s >= 24 ? 24 : 16;
}

const tdotCounty = (p: Record<string, unknown>): string => {
  const locs = p.locations;
  if (Array.isArray(locs) && locs[0] && typeof locs[0] === "object") {
    return str((locs[0] as Record<string, unknown>).countyName);
  }
  return "";
};

// ---- per-source config -------------------------------------------------------
// The backend is source-agnostic; the only source-specific knowledge is here:
// each source's categories, their colors, and how to pull a title / location /
// jurisdiction / detail rows out of a feature's properties. Features carry their
// own `source`, so every render looks up config per-feature (see cfgFor) — that's
// what lets several sources be shown on the map at once.
export const SOURCES: Record<string, SourceConfig> = {
  hc911: {
    name: "Hamilton County 911",
    short: "911",
    categories: ["police", "fire", "ems", "other"],
    colors: {
      police: "#2563eb",
      fire: "#dc2626",
      ems: "#059669",
      other: "#6b7280",
    },
    title: (p) => str(p.label) || str(p.type) || "Incident",
    location: (p) => str(p.location),
    jurisdiction: (p) => str(p.jurisdiction),
    detail: (p, d) => [
      ["Status", p.status],
      ["Agency", p.agency_type],
      ["Jurisdiction", p.jurisdiction],
      ["Location", p.location],
      ["Cross streets", p.crossstreets],
      ["City", p.city],
      ["Priority", p.priority],
      ["Incident #", p.sequencenumber],
      ["Active", String(d.is_active)],
    ],
  },
  tdot: {
    name: "TDOT SmartWay",
    short: "TDOT",
    categories: ["incident", "construction", "special_event", "severe"],
    colors: {
      incident: "#2563eb",
      construction: "#d97706",
      special_event: "#7c3aed",
      severe: "#dc2626",
    },
    title: (p) => str(p.label) || str(p.eventTypeName) || "Event",
    location: (p) => str(p.description) || tdotCounty(p),
    jurisdiction: (p) => tdotCounty(p),
    detail: (p, d) => [
      ["Status", p.status],
      ["Type", p.eventTypeName],
      ["Subtype", p.eventSubTypeDescription],
      ["Direction", p.directionDescription],
      ["Impact", p.impactDescription],
      ["County", tdotCounty(p)],
      ["Route mile", p.mileMarker],
      ["Severe", p.isSevere ? "Yes" : null],
      ["Active", String(d.is_active)],
      ["Description", p.description],
    ],
  },
  epb: {
    name: "EPB Outages",
    short: "EPB",
    categories: ["energy", "fiber"],
    colors: { energy: "#d97706", fiber: "#0891b2" },
    // EPB's map colors a marker by outage status and sizes it by customers affected,
    // shown as a round dot rather than the default teardrop pin.
    round: true,
    markerColor: (p) => EPB_STATUS_COLORS[str(p.status)] || "#666666",
    markerSize: epbMarkerSize,
    title: (p) =>
      str(p.label) ||
      (p.service === "fiber" ? "Fiber Outage" : "Energy Outage"),
    location: () => "",
    jurisdiction: (p) => cap(str(p.service)),
    detail: (p, d) => [
      ["Status", catLabel(str(p.status))],
      ["Service", cap(str(p.service))],
      ["Customers affected", p.customer_quantity],
      ["Active", String(d.is_active)],
    ],
  },
};

// Fallback for a feature whose source has no client config (shouldn't happen).
export const FALLBACK: SourceConfig = {
  name: "Unknown",
  short: "?",
  categories: [],
  colors: {},
  title: (p) => str(p.label) || "Item",
  location: (p) => str(p.location),
  jurisdiction: (p) => str(p.jurisdiction),
  detail: (p, d) => [
    ["Status", p.status],
    ["Active", String(d.is_active)],
  ],
};

export const cfgFor = (key: string): SourceConfig => SOURCES[key] || FALLBACK;

// ---- display helpers ---------------------------------------------------------
export const isClosed = (f: TrackedFeature): boolean =>
  f.properties.active === false;
export const catLabel = (cat: string): string =>
  cap(String(cat || "").replace(/_/g, " "));
export const colorFor = (sourceKey: string, cat: string): string =>
  cfgFor(sourceKey).colors[cat] || "#6b7280";

// A feature's display color: a source may color by status/properties (e.g. EPB
// outage status); otherwise fall back to its category color.
export const featureColor = (f: TrackedFeature): string => {
  const cfg = cfgFor(f.properties.source);
  return cfg.markerColor
    ? cfg.markerColor(f.properties)
    : colorFor(f.properties.source, f.properties.category);
};
