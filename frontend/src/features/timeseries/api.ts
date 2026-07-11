import { getJSON, type FeatureCollection } from "../../lib/api";
import { SOURCES, cfgFor } from "./sources";
import { ts } from "./state.svelte";
import type { EntityDetail, EntityId, TrackedFeature, TrackPoint } from "./types";

export const fetchEntity = (id: EntityId): Promise<EntityDetail> =>
  getJSON<EntityDetail>(`/api/v1/timeseries/entities/${id}`);

export const fetchTrack = (id: EntityId): Promise<TrackPoint[]> =>
  getJSON<TrackPoint[]>(`/api/v1/timeseries/entities/${id}/track`);

export async function fetchSourceInto(key: string): Promise<void> {
  let url = `/api/v1/timeseries/entities?source=${key}`;
  if (ts.showClosed) url += `&closed_within=${ts.closedWindow}`;
  const fc = await getJSON<FeatureCollection<TrackedFeature>>(url);
  for (const f of fc.features) ts.features.set(f.id, f);
}

/** Reload every selected source from scratch (first load + closed-window changes). */
export async function loadActive(): Promise<void> {
  ts.features.clear();
  await Promise.all([...ts.selectedSources].map(fetchSourceInto));
}

export async function toggleSource(key: string, on: boolean): Promise<void> {
  if (!SOURCES[key]) return;
  if (on) {
    ts.selectedSources.add(key);
    for (const c of cfgFor(key).categories) ts.categories.add(c); // show its categories
    await fetchSourceInto(key);
  } else {
    ts.selectedSources.delete(key);
    const stillVisible = new Set(ts.selectedCategoryList);
    for (const c of cfgFor(key).categories) if (!stillVisible.has(c)) ts.categories.delete(c);
    for (const [id, f] of [...ts.features]) if (f.properties.source === key) ts.features.delete(id);
  }
}
