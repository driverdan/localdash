import { getJSON } from "../../lib/api";
import { setCategoryLabels } from "../news";
import type { Story } from "../news";
import type { EventItem } from "../events";
import { home } from "./state.svelte";

interface StoriesResponse {
  categories: Record<string, string>;
  stories: Story[];
}

// Shape of /api/v1/weather/current (app/api/weather.py): NWS station
// observation + the leading forecast periods, names passed through verbatim.
export interface WeatherCurrent {
  temperature_f: number;
  description: string;
  icon: string | null;
  wind_mph: number | null;
  wind_direction: string | null;
  humidity_percent: number | null;
  observed_at: string | null;
}

export interface WeatherPeriod {
  name: string;
  temperature: number;
  temperature_unit: string;
  precip_percent: number | null;
  short_forecast: string;
  detailed_forecast: string;
}

// AirNow overall AQI (worst pollutant); null when AirNow is unconfigured,
// unreachable, or reports nothing usable. category is the EPA number (1-6),
// the chip's color key; category_name is display text passed through verbatim.
export interface WeatherAqi {
  value: number;
  category: number | null;
  category_name: string | null;
  pollutant: string | null;
}

export interface Weather {
  current: WeatherCurrent | null;
  periods: WeatherPeriod[];
  aqi: WeatherAqi | null;
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

/** Load the weather strip: current conditions + today's leading forecast
 *  periods. A partial payload (either half missing) still resolves — the strip
 *  renders whichever half is present. */
export async function loadWeather(): Promise<void> {
  try {
    home.weather = await getJSON<Weather>("/api/v1/weather/current");
    home.weatherError = false;
  } catch {
    home.weatherError = true;
  } finally {
    home.weatherLoaded = true;
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
