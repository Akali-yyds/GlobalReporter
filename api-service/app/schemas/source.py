"""
Source schema definitions.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NewsSourceResponse(BaseModel):
    """Serialized source row."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    code: str
    base_url: str
    country: str
    language: str
    category: str
    source_tier: str
    is_active: bool


class SourceTierAnalyticsItem(BaseModel):
    source_tier: str
    source_count: int
    active_source_count: int
    article_count: int
    event_count: int
    recent_job_count: int
    successful_job_count: int
    success_rate: float
    avg_event_heat: float
    publish_time_coverage: float
    fresh_article_ratio: float
    tag_coverage_ratio: float
    low_signal_ratio: float
    geo_coverage_ratio: float
    region_yield_ratio: float
    last_job_started_at: datetime | None = None
    last_success_at: datetime | None = None
    latest_publish_at: datetime | None = None
    latest_event_at: datetime | None = None


class SourceAnalyticsItem(BaseModel):
    code: str
    name: str
    source_tier: str
    is_active: bool
    article_count: int
    event_count: int
    recent_job_count: int
    successful_job_count: int
    success_rate: float
    avg_event_heat: float
    publish_time_coverage: float
    fresh_article_ratio: float
    tag_coverage_ratio: float
    low_signal_ratio: float
    geo_coverage_ratio: float
    region_yield_ratio: float
    last_job_status: str | None = None
    last_job_started_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error_message: str | None = None
    latest_publish_at: datetime | None = None
    latest_event_at: datetime | None = None


class SourceAnalyticsResponse(BaseModel):
    since_hours: int | None = None
    freshness_hours: int
    tiers: list[SourceTierAnalyticsItem]
    sources: list[SourceAnalyticsItem]
