// Shapes returned by /api/v1/news/* (see app/api/news.py + app/news/stories.py).

export interface SourceLink {
  source: string;
  slug: string;
  title: string;
  url: string;
  published: string;
}

export interface Story {
  id: number;
  title: string;
  summary: string;
  category: string;
  first_published: string;
  latest_published: string;
  source_count: number;
  article_count: number;
  sources: SourceLink[];
}

export interface StoriesResponse {
  /** category slug -> display label, in display order */
  categories: Record<string, string>;
  stories: Story[];
}

export interface FeedHealth {
  slug: string;
  name: string;
  homepage: string;
  enabled: boolean;
  category: string;
  last_fetch: string | null;
  last_status: string | null;
  article_count: number;
}

export interface SourcesResponse {
  sources: FeedHealth[];
}
