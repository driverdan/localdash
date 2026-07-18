import { cap } from "../../lib/format";
import type { IconName } from "../../lib/icons";
import type { SourceConfig, TrackedFeature, TrackedProperties } from "./types";

// Glyph shown when a category has no configured icon (or its source is unknown).
export const FALLBACK_ICON: IconName = "map-pin";

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

// American Water advisory headers read "City: Short summary : long message…" —
// keep the "City: Short summary" lead as the title.
const advisoryTitle = (p: Record<string, unknown>): string => {
  const header = str(p.EventHeader);
  if (header) return header.split(" : ")[0].trim();
  return str(p.EventType) || "Advisory";
};

// Epoch-millis field -> a short local date (empty when missing/invalid).
const advisoryDate = (v: unknown): string => {
  const n = Number(v);
  return Number.isFinite(n) && n > 0 ? new Date(n).toLocaleDateString() : "";
};

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
    icons: {
      police: "siren",
      fire: "flame",
      ems: "ambulance",
      other: "circle-question-mark",
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
    icons: {
      incident: "triangle-alert",
      construction: "traffic-cone",
      special_event: "party-popper",
      severe: "octagon-alert",
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
    icons: { energy: "zap", fiber: "cable" },
    statusLabels: {
      OUTAGE_REPORTED: "Outage",
      EN_ROUTE: "En Route",
      REPAIR_IN_PROGRESS: "Repairing",
      RESTORED: "Restored",
      Closed: "Closed",
    },
    // EPB's map colors a marker by outage status and sizes it by customers affected,
    // so its glyph is tinted by status (not category) and scaled by markerSize.
    markerColor: (p) => EPB_STATUS_COLORS[str(p.status)] || "#666666",
    markerSize: epbMarkerSize,
    title: (p) =>
      str(p.label) ||
      (p.service === "fiber" ? "Fiber Outage" : "Energy Outage"),
    location: () => "",
    jurisdiction: (p) => cap(str(p.service)),
    detail: (p, d) => [
      ["Status", statusLabel("epb", p.status)],
      ["Service", cap(str(p.service))],
      ["Customers affected", p.customer_quantity],
      ["Active", String(d.is_active)],
    ],
  },
  tnaw: {
    name: "TN American Water Advisories",
    short: "TAW",
    categories: ["emergency", "general"],
    colors: { emergency: "#dc2626", general: "#0891b2" },
    icons: { emergency: "octagon-alert", general: "droplet" },
    title: advisoryTitle,
    location: (p) => str(p.EventMessage).slice(0, 140),
    jurisdiction: (p) => catLabel(str(p.advisory_type)),
    detail: (p, d) => [
      ["Type", p.EventType],
      ["Notification", p.EventNotificationType],
      ["Started", advisoryDate(p.EventStartDate)],
      ["Est. completion", advisoryDate(p.EventCompletionDate)],
      ["Details", p.EventHyperlink],
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
  icons: {},
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
// Category identity is scoped to its source ("source:category"), so two sources
// may define the same category name without sharing a filter toggle or color.
export const catKey = (source: string, cat: string): string =>
  `${source}:${cat}`;
export const catLabel = (cat: string): string =>
  cap(String(cat || "").replace(/_/g, " "));
// Humanize a feature's raw `status` for display. A source may map its status
// codes via `statusLabels` (e.g. EPB's OUTAGE_REPORTED -> "Outage"); anything
// unmapped falls back to the generic catLabel humanizer.
export const statusLabel = (source: string, raw: unknown): string =>
  cfgFor(source).statusLabels?.[str(raw)] ?? catLabel(str(raw));
// Source-agnostic variant for surfaces that render a pooled/per-feature status
// without a paired source (map popup, tooltip, table, detail history, filter
// dropdown): resolve against any source's statusLabels, else catLabel. No two
// sources define the same raw code today, so the scan is unambiguous.
export const statusLabelForRaw = (raw: unknown): string => {
  const code = str(raw);
  if (!code) return "";
  for (const cfg of Object.values(SOURCES)) {
    const label = cfg.statusLabels?.[code];
    if (label) return label;
  }
  return catLabel(code);
};
export const colorFor = (sourceKey: string, cat: string): string =>
  cfgFor(sourceKey).colors[cat] || "#6b7280";
export const iconFor = (sourceKey: string, cat: string): IconName =>
  cfgFor(sourceKey).icons[cat] || FALLBACK_ICON;

// A feature's display color: a source may color by status/properties (e.g. EPB
// outage status); otherwise fall back to its category color.
export const featureColor = (f: TrackedFeature): string => {
  const cfg = cfgFor(f.properties.source);
  return cfg.markerColor
    ? cfg.markerColor(f.properties)
    : colorFor(f.properties.source, f.properties.category);
};
