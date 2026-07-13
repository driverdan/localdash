import { getJSON } from "../../lib/api";
import { events } from "./state.svelte";
import type { ItemsResponse, TagsResponse } from "./types";

function itemsURL(): string {
  const params = new URLSearchParams();
  for (const t of events.topics) params.append("topic", t);
  if (events.maxMiles !== null) params.set("max_miles", String(events.maxMiles));
  if (events.search.trim()) params.set("search", events.search.trim());
  const qs = params.toString();
  return "/api/v1/events/items" + (qs ? `?${qs}` : "");
}

export async function loadItems(): Promise<void> {
  try {
    const data = await getJSON<ItemsResponse>(itemsURL());
    events.items = data.items;
    events.loadError = false;
  } catch {
    events.loadError = true;
  }
}

export async function loadTags(): Promise<void> {
  const data = await getJSON<TagsResponse>("/api/v1/events/tags");
  events.tags = data.tags;
  // Restored topics may name tags that no longer exist; drop them and refetch
  // so the list isn't filtered on chips the user can't even see.
  const known = new Set(data.tags);
  const kept = events.topics.filter((t) => known.has(t));
  if (kept.length !== events.topics.length) {
    events.topics = kept;
    await loadItems();
  }
}

/** Trigger a server-side fetch of all configured sources, then reload the view. */
export async function refreshSources(): Promise<void> {
  events.refreshing = true;
  events.statusText = "Fetching sources…";
  try {
    const r = await fetch("/api/v1/events/refresh", { method: "POST" });
    if (!r.ok) throw new Error(`refresh -> ${r.status}`);
    await Promise.all([loadItems(), loadTags()]);
    events.statusText = "Updated " + new Date().toLocaleTimeString();
  } catch {
    events.statusText = "Refresh failed";
  } finally {
    events.refreshing = false;
  }
}
