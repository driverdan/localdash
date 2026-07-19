import { getJSON } from "../../lib/api";
import { isLocalToday } from "../../lib/format";
import type { FeatureCollection } from "../../lib/api";
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
  // Observation time of the reading (AirNow reports hourly). May be older than
  // the rest of the payload when a transient AirNow failure carried it forward.
  observed_at: string | null;
}

export interface Weather {
  current: WeatherCurrent | null;
  periods: WeatherPeriod[];
  aqi: WeatherAqi | null;
}

// Per-service rollup of active EPB outages, computed client-side from the
// timeseries entities endpoint (active-only default). `customers` sums each
// outage's customer_quantity; missing/non-positive values count as zero.
export interface OutageCounts {
  count: number;
  customers: number;
}

export interface OutageSummary {
  energy: OutageCounts;
  fiber: OutageCounts;
}

// The one slice of a timeseries entity feature the digest reads.
interface OutageFeature {
  properties: { category?: string | null; customer_quantity?: unknown };
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

/** Load the outages digest: reduce the active EPB entities to per-service
 *  counts + customers affected. The endpoint is active-only by default, so an
 *  empty collection is the "no current outages" happy state, not an error. */
export async function loadOutages(): Promise<void> {
  try {
    const data = await getJSON<FeatureCollection<OutageFeature>>(
      "/api/v1/timeseries/entities?source=epb",
    );
    const summary: OutageSummary = {
      energy: { count: 0, customers: 0 },
      fiber: { count: 0, customers: 0 },
    };
    for (const feature of data.features) {
      const { category, customer_quantity } = feature.properties;
      if (category !== "energy" && category !== "fiber") continue;
      summary[category].count += 1;
      if (typeof customer_quantity === "number" && customer_quantity > 0) {
        summary[category].customers += customer_quantity;
      }
    }
    home.outages = summary;
    home.outagesError = false;
  } catch {
    home.outagesError = true;
  } finally {
    home.outagesLoaded = true;
  }
}

/** Load the today's-events digest: of the upcoming events within a fixed 35-mile
 *  cap of the configured center, keep only those starting on the viewer's current
 *  local calendar day. The request is unchanged (up to 10, soonest first); since
 *  the endpoint orders by start ascending, same-day events lead the list, so the
 *  limit acts as a display cap on the today subset. Saved topic/search/distance
 *  preferences from the events page are ignored. */
export async function loadEvents(): Promise<void> {
  try {
    const data = await getJSON<ItemsResponse>(
      "/api/v1/events/items?limit=10&max_miles=35",
    );
    home.events = data.items.filter((item) => isLocalToday(item.starts_at));
    home.eventsError = false;
  } catch {
    home.eventsError = true;
  } finally {
    home.eventsLoaded = true;
  }
}
