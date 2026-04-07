"""
Event schema definitions.
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class EventGeoMappingResponse(BaseModel):
    """Schema for event-geo mapping response."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_id: str
    geo_id: str
    geo_key: str
    confidence: float
    matched_text: Optional[str] = None
    extraction_method: Optional[str] = None
    relevance_score: Optional[float] = None
    is_primary: bool = False
    source_text_position: Optional[str] = None
    geo_type: Optional[str] = None
    display_type: Optional[str] = None
    geo_name: Optional[str] = None


class NewsEventBase(BaseModel):
    """Base news event schema."""
    title: str
    summary: Optional[str] = None
    main_country: str
    event_level: str = "country"
    source_code: Optional[str] = None
    source_class: str = "news"
    heat_score: int = 0
    severity: int = 0
    confidence: int = 100
    article_count: int = 0
    category: Optional[str] = None
    geo: Optional[str] = None
    geom_type: Optional[str] = None
    raw_geometry: Optional[dict] = None
    display_geo: Optional[dict] = None
    bbox: Optional[list[float]] = None
    source_metadata: Optional[dict] = None
    tags: List[str] = Field(default_factory=list)
    source_tier: str = "authoritative"
    source_tier_level: int = 2
    freshness_sla_hours: int = 24
    event_time: Optional[datetime] = None
    event_status: str = "closed"
    closed_at: Optional[datetime] = None
    source_updated_at: Optional[datetime] = None
    license_mode: str = "public_web"
    canonical_url: Optional[str] = None
    external_id: Optional[str] = None


class NewsEventListItem(NewsEventBase):
    """News event row for list endpoints (no nested relations)."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    title_hash: str
    first_seen_at: datetime
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime


class RelatedSourceItem(BaseModel):
    """One source / article link tied to an event."""
    source_name: str
    source_code: str
    article_url: str


class NewsEventResponse(NewsEventBase):
    """Schema for news event detail response."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    title_hash: str
    first_seen_at: datetime
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime
    geo_mappings: List[EventGeoMappingResponse] = Field(default_factory=list)
    primary_article_url: Optional[str] = None
    primary_source_name: Optional[str] = None
    primary_source_code: Optional[str] = None
    primary_source_url: Optional[str] = None
    related_sources: List[RelatedSourceItem] = Field(default_factory=list)


class NewsEventListResponse(BaseModel):
    """Schema for news event list response."""
    total: int
    page: int
    page_size: int
    items: List[NewsEventListItem]
