export type VideoType = 'youtube_embed' | 'hls';
export type VideoRolloutState = 'draft' | 'poc' | 'canary' | 'default' | 'paused';
export type VideoStatus = 'unknown' | 'live' | 'offline' | 'error';

export interface VideoProbeCheckpoint {
  id: string;
  source_code: string;
  job_code: string;
  last_probe_at?: string | null;
  last_success_at?: string | null;
  last_http_status?: number | null;
  last_error?: string | null;
  is_live: boolean;
  last_title?: string | null;
  last_thumbnail?: string | null;
  consecutive_failures: number;
}

export interface VideoSource {
  id: string;
  source_code: string;
  display_name: string;
  video_type: VideoType;
  provider: string;
  channel_or_stream_id?: string | null;
  embed_url?: string | null;
  playback_url?: string | null;
  thumbnail_url?: string | null;
  title?: string | null;
  description?: string | null;
  region?: string | null;
  country?: string | null;
  city?: string | null;
  topic_tags: string[];
  license_mode: string;
  priority: number;
  enabled: boolean;
  rollout_state: VideoRolloutState;
  status: VideoStatus;
  notes?: string | null;
  source_metadata: Record<string, unknown>;
  checkpoint?: VideoProbeCheckpoint | null;
}

export interface VideoHealthResponse {
  sources: VideoSource[];
}

export interface VideoProbeResponse {
  ok: boolean;
  source_code: string;
  job_code: string;
  status: VideoStatus;
  is_live: boolean;
  http_status?: number | null;
  title?: string | null;
  thumbnail_url?: string | null;
  error?: string | null;
}
