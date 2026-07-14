// Feature-agnostic API plumbing: typed fetch + the /api/v1 app-shell endpoints
// and the GeoJSON envelope every geographic response uses.

export interface FeatureCollection<F> {
  type: "FeatureCollection";
  features: F[];
}

export interface AppConfig {
  tile_url: string;
  tile_attribution: string;
}

export async function getJSON<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`GET ${url} -> ${r.status}`);
  return r.json() as Promise<T>;
}

export const fetchConfig = (): Promise<AppConfig> =>
  getJSON<AppConfig>("/api/v1/config");
