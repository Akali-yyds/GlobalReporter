// Type definitions for news data

export interface NewsArticle {
  id: string;
  title: string;
  summary: string;
  content?: string;
  source_name: string;
  source_url: string;
  article_url: string;
  publish_time: string;
  crawl_time: string;
  heat_score: number;
  category: string;
  language: string;
  country_tags: string[];
  city_tags: string[];
  region_tags: string[];
}

export interface NewsEvent {
  id: string;
  title: string;
  summary: string;
  main_country: string;
  event_level: 'country' | 'city' | 'region';
  heat_score: number;
  article_count: number;
  category?: string;
  title_hash?: string;
  geo_mappings?: GeoMapping[];
  first_seen_at: string;
  last_seen_at: string;
  created_at?: string;
  updated_at?: string;
  /** Present on GET /news/events/:id */
  primary_article_url?: string | null;
  primary_source_name?: string | null;
  primary_source_code?: string | null;
  primary_source_url?: string | null;
  related_sources?: RelatedSource[];
}

export interface RelatedSource {
  source_name: string;
  source_code: string;
  article_url: string;
}

export interface GeoMapping {
  id: string;
  event_id: string;
  geo_id: string;
  geo_key: string;
  geo_type: 'country' | 'city' | 'region';
  display_type: 'polygon' | 'point' | 'ring';
  confidence: number;
  geo_name?: string;
  matched_text?: string;
  is_primary?: boolean;
  extraction_method?: string;
  relevance_score?: number;
}

export interface NewsSource {
  id: string;
  name: string;
  code: string;
  base_url: string;
  country: string;
  language: string;
  category: string;
  is_active: boolean;
}

export interface CrawlJob {
  id: string;
  source_id: string;
  spider_name: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  items_crawled: number;
  items_processed: number;
  error_message?: string;
  started_at: string;
  finished_at?: string;
}

// API response types
export interface PaginatedResponse<T> {
  total: number;
  page: number;
  page_size: number;
  items: T[];
}

export interface Hotspot {
  event_id: string;
  geo_key: string;
  geo_name?: string;
  geo_type: 'country' | 'city' | 'region';
  display_type: 'polygon' | 'point' | 'ring';
  heat_score: number;
  color?: string;
  size?: number;
  polygon?: [number, number][];
  center?: [number, number];
  /** Natural Earth ISO_A3 — used to tint country polygons */
  iso_a3?: string | null;
  title: string;
  summary?: string;
  confidence: number;
}

export interface HotspotListResponse {
  hotspots: Hotspot[];
}

export interface CountryHotspotItem {
  country_code: string;
  country_name?: string;
  iso_a3?: string;
  heat_total: number;
  event_count: number;
  center?: [number, number];
}

export interface CountryHotspotListResponse {
  total: number;
  countries: CountryHotspotItem[];
}

export interface Admin1HotspotItem {
  admin1_code?: string;
  admin1_name?: string;
  geo_key?: string;
  heat_total: number;
  event_count: number;
  center?: [number, number];
}

export interface Admin1HotspotListResponse {
  country_code: string;
  total: number;
  admin1_list: Admin1HotspotItem[];
}

export interface CityHotspotItem {
  city_name?: string;
  admin1_name?: string;
  geo_key?: string;
  heat_total: number;
  event_count: number;
  center?: [number, number];
}

export interface CityHotspotListResponse {
  country_code: string;
  total: number;
  cities: CityHotspotItem[];
}
