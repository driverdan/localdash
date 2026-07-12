// Shapes returned by /api/v1/events/* (see app/api/events.py).

export interface EventLink {
  source_name: string;
  source_url: string;
}

export interface EventItem {
  id: number;
  title: string;
  description: string;
  starts_at: string;
  ends_at: string | null;
  venue_name: string | null;
  address: string | null;
  latitude: number | null;
  longitude: number | null;
  tags: string[];
  links: EventLink[];
  distance_miles: number | null;
}

export interface ItemsResponse {
  count: number;
  origin: { lat: number; lon: number };
  items: EventItem[];
}

export interface TagsResponse {
  tags: string[];
}
