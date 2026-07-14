import { getJSON, type FeatureCollection } from "../../lib/api";
import { SOURCES, catKey, cfgFor } from "./sources";
import { ts } from "./state.svelte";
import type {
  EntityDetail,
  EntityId,
  TrackedFeature,
  TrackPoint,
} from "./types";

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

// Remove a source's entities from the map/table (it is no longer loaded).
function dropSource(key: string): void {
  for (const [id, f] of [...ts.features])
    if (f.properties.source === key) ts.features.delete(id);
}

/** Parent toggle: select/clear all of a source's categories, fetching or dropping it. */
export async function toggleSource(key: string, on: boolean): Promise<void> {
  if (!SOURCES[key]) return;
  const cats = cfgFor(key).categories;
  if (on) {
    for (const c of cats) ts.categories.add(catKey(key, c));
    await fetchSourceInto(key);
  } else {
    for (const c of cats) ts.categories.delete(catKey(key, c));
    dropSource(key);
  }
}

/**
 * Child toggle: enable/disable one source-scoped category. The source is fetched
 * when this is its first enabled category and dropped when it was its last.
 */
export async function toggleCategory(
  source: string,
  cat: string,
  on: boolean,
): Promise<void> {
  if (!SOURCES[source]) return;
  if (on) {
    const wasLoaded = ts.selectedSources.has(source);
    ts.categories.add(catKey(source, cat));
    if (!wasLoaded) await fetchSourceInto(source);
  } else {
    ts.categories.delete(catKey(source, cat));
    if (!ts.selectedSources.has(source)) dropSource(source);
  }
}
