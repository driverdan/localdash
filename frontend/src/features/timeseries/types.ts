// The typed boundary of the timeseries feature: the GeoJSON feature contract the
// API guarantees, plus the shape of per-source display config. Source-specific
// properties stay untyped (Record) — that's the source-agnostic seam.

import type { IconName } from "../../lib/icons";

export type EntityId = string | number;

/** GeoJSON geometry the API may emit — a point for point sources, or a polygon
 *  area for sources like `tnaw` water advisories. */
export type GeoGeometry =
  | { type: "Point"; coordinates: [number, number] }
  | { type: "Polygon"; coordinates: number[][][] }
  | { type: "MultiPolygon"; coordinates: number[][][][] };

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
  geometry: GeoGeometry | null;
  properties: TrackedProperties;
}

export interface TrackPoint {
  observed_at: string;
  status: string | null;
  /** Full geometry of the observation (point or polygon). */
  geometry: GeoGeometry | null;
  /** Convenience scalars, populated only for point geometry (null otherwise). */
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

/** Diff pushed on the global /api/v1/ws bus after each poll cycle. */
export interface DiffMessage {
  topic: "timeseries";
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
  /** Per-category marker glyph (Lucide icon name). */
  icons: Record<string, IconName>;
  /** Color by status/properties (e.g. EPB outage status) instead of category. */
  markerColor?: (p: TrackedProperties) => string;
  /** Scale the glyph per-feature (e.g. EPB by customers affected). */
  markerSize?: (p: TrackedProperties) => number;
  title: (p: Record<string, unknown>) => string;
  location: (p: Record<string, unknown>) => string;
  jurisdiction: (p: Record<string, unknown>) => string;
  detail: (p: Record<string, unknown>, d: EntityDetail) => DetailRow[];
}
