import { getJSON } from "../../lib/api";
import { setCategoryLabels } from "../news";
import type { Story } from "../news";
import type { EventItem } from "../events";
import { home } from "./state.svelte";

interface StoriesResponse {
  categories: Record<string, string>;
  stories: Story[];
}

interface ItemsResponse {
  items: EventItem[];
}

/** Load the latest-news digest: 5 newest stories, ignoring news preferences.
 *  The response's category map feeds StoryCard's shared label lookup so badges
 *  read as labels even on a cold session that never opened /news. */
export async function loadStories(): Promise<void> {
  try {
    const data = await getJSON<StoriesResponse>("/api/v1/news/stories?limit=5");
    setCategoryLabels(data.categories);
    home.stories = data.stories;
    home.storiesError = false;
  } catch {
    home.storiesError = true;
  } finally {
    home.storiesLoaded = true;
  }
}

/** Load the upcoming-events digest: next 5 events with no filter params, so
 *  saved topic/distance preferences from the events page are ignored. */
export async function loadEvents(): Promise<void> {
  try {
    const data = await getJSON<ItemsResponse>("/api/v1/events/items?limit=5");
    home.events = data.items;
    home.eventsError = false;
  } catch {
    home.eventsError = true;
  } finally {
    home.eventsLoaded = true;
  }
}
