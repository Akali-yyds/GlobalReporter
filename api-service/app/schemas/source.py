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
    source_class: str
    source_tier: str
    source_tier_level: int
    freshness_sla_hours: int
    license_mode: str
    is_active: bool


class SourcePolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_code: str
    source_class: str
    enabled: bool
    fetch_mode: str
    schedule_minutes: int
    freshness_sla_hours: int
    dedup_key_mode: str
    event_time_field_priority: list[str]
    severity_mapping_rule: str | None = None
    geo_precision_rule: str | None = None
    default_params_json: dict
    license_mode: str
    notes: str | None = None


class SourceFeedProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_code: str
    feed_code: str
    feed_url: str
    feed_name: str
    priority: int
    freshness_sla_hours: int
    rollout_state: str
    enabled: bool
    expected_update_interval_hours: int
    license_mode: str
    notes: str | None = None


class SourceFeedProfilePatchRequest(BaseModel):
    priority: int | None = None
    freshness_sla_hours: int | None = None
    rollout_state: str | None = None
    enabled: bool | None = None
    expected_update_interval_hours: int | None = None
    license_mode: str | None = None
    notes: str | None = None


class SourceFeedPromoteRequest(BaseModel):
    target_state: str | None = None


class SourceFeedHealthItem(BaseModel):
    feed_profile_id: str | None = None
    source_code: str
    feed_code: str
    feed_name: str
    feed_url: str
    priority: int
    freshness_sla_hours: int
    rollout_state: str
    enabled: bool
    expected_update_interval_hours: int
    license_mode: str
    last_fetch_at: datetime | None = None
    last_success_at: datetime | None = None
    last_fresh_item_at: datetime | None = None
    last_http_status: int | None = None
    last_error: str | None = None
    scraped_count_24h: int
    dropped_stale_count_24h: int
    dropped_quality_count_24h: int
    stale_ratio_24h: float
    direct_ok_rate_24h: float
    consecutive_failures: int


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
    source_class: str
    source_tier: str
    source_tier_level: int
    freshness_sla_hours: int
    license_mode: str
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
