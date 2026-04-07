"""Video API schema definitions."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class VideoSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_code: str
    display_name: str
    video_type: str
    provider: str
    channel_or_stream_id: str | None = None
    embed_url: str | None = None
    playback_url: str | None = None
    thumbnail_url: str | None = None
    title: str | None = None
    description: str | None = None
    region: str | None = None
    country: str | None = None
    city: str | None = None
    topic_tags: list[str]
    license_mode: str
    priority: int
    enabled: bool
    rollout_state: str
    status: str
    notes: str | None = None
    source_metadata: dict


class VideoSourcePatchRequest(BaseModel):
    display_name: str | None = None
    embed_url: str | None = None
    playback_url: str | None = None
    thumbnail_url: str | None = None
    title: str | None = None
    description: str | None = None
    region: str | None = None
    country: str | None = None
    city: str | None = None
    topic_tags: list[str] | None = None
    license_mode: str | None = None
    priority: int | None = None
    enabled: bool | None = None
    rollout_state: str | None = None
    status: str | None = None
    notes: str | None = None
    source_metadata: dict | None = None


class VideoProbeCheckpointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_code: str
    job_code: str
    last_probe_at: datetime | None = None
    last_success_at: datetime | None = None
    last_http_status: int | None = None
    last_error: str | None = None
    is_live: bool
    last_title: str | None = None
    last_thumbnail: str | None = None
    consecutive_failures: int


class VideoSourceWithHealthResponse(VideoSourceResponse):
    checkpoint: VideoProbeCheckpointResponse | None = None


class VideoHealthResponse(BaseModel):
    sources: list[VideoSourceWithHealthResponse]


class VideoProbeResponse(BaseModel):
    ok: bool
    source_code: str
    job_code: str
    status: str
    is_live: bool
    http_status: int | None = None
    title: str | None = None
    thumbnail_url: str | None = None
    error: str | None = None
