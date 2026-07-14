import { getJSON } from "../../lib/api";
import { news } from "./state.svelte";
import type { SourcesResponse, StoriesResponse } from "./types";

export async function loadStories(): Promise<void> {
  try {
    const data = await getJSON<StoriesResponse>(
      `/api/v1/news/stories?hours=${news.hours}`,
    );
    news.categories = data.categories;
    news.stories = data.stories;
    news.loadError = false;
  } catch {
    news.loadError = true;
  }
}

export async function loadSources(): Promise<void> {
  const data = await getJSON<SourcesResponse>("/api/v1/news/sources");
  news.sources = data.sources;
}

/** Trigger a server-side fetch+recluster cycle, then reload the view. */
export async function refreshFeeds(): Promise<void> {
  news.refreshing = true;
  news.statusText = "Fetching feeds…";
  try {
    const r = await fetch("/api/v1/news/refresh", { method: "POST" });
    if (!r.ok) throw new Error(`refresh -> ${r.status}`);
    await Promise.all([loadStories(), loadSources()]);
    news.statusText = "Updated " + new Date().toLocaleTimeString();
  } catch {
    news.statusText = "Refresh failed";
  } finally {
    news.refreshing = false;
  }
}
