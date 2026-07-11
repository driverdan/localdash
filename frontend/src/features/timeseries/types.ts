// The typed boundary of the timeseries feature: the GeoJSON feature contract the
// API guarantees, plus the shape of per-source display config. Source-specific
// properties stay untyped (Record) — that's the source-agnostic seam.

export type EntityId = string | number;

/** Loose property bag: authoritative keys are typed, source-specific ones are unknown. */
export interface TrackedProperties {
  id: EntityId;
  source: string;
  external_id: string;
  category: string;
  label?: string | null;
  last_seen_at?: string | null;
  active: boolean;
  status?: string | null;
  [key: string]: unknown;
}

export interface TrackedFeature {
  type: "Feature";
  id: EntityId;
  geometry: { type: "Point"; coordinates: [number, number] } | null;
  properties: TrackedProperties;
}

export interface TrackPoint {
  observed_at: string;
  status: string | null;
  lon: number | null;
  lat: number | null;
  properties: Record<string, unknown>;
}

/** Snapshot from GET /api/v1/timeseries/entities/{id} (no track embedded). */
export interface EntityDetail {
  id: EntityId;
  source: string;
  external_id: string;
  category: string;
  label: string | null;
  is_active: boolean;
  first_seen_at: string;
  last_seen_at: string;
  latest_properties: Record<string, unknown>;
}

/** Diff pushed over /api/v1/timeseries/ws after each poll cycle. */
export interface DiffMessage {
  type: "diff";
  source: string;
  new: TrackedFeature[];
  updated: TrackedFeature[];
  closed: EntityId[];
}

export type DetailRow = [string, unknown];

/** Per-source display config — the only place source-specific knowledge lives. */
export interface SourceConfig {
  name: string;
  short: string;
  categories: string[];
  colors: Record<string, string>;
  /** Round dot (sized per-source) instead of the default teardrop pin. */
  round?: boolean;
  /** Color by status/properties (e.g. EPB outage status) instead of category. */
  markerColor?: (p: TrackedProperties) => string;
  markerSize?: (p: TrackedProperties) => number;
  title: (p: Record<string, unknown>) => string;
  location: (p: Record<string, unknown>) => string;
  jurisdiction: (p: Record<string, unknown>) => string;
  detail: (p: Record<string, unknown>, d: EntityDetail) => DetailRow[];
}
