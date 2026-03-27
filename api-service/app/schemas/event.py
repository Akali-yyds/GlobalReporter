"""
Event schema definitions.
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict


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
    heat_score: int = 0
    article_count: int = 0
    category: Optional[str] = None


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
    geo_mappings: List[EventGeoMappingResponse] = []
    primary_article_url: Optional[str] = None
    primary_source_name: Optional[str] = None
    primary_source_code: Optional[str] = None
    primary_source_url: Optional[str] = None
    related_sources: List[RelatedSourceItem] = []


class NewsEventListResponse(BaseModel):
    """Schema for news event list response."""
    total: int
    page: int
    page_size: int
    items: List[NewsEventListItem]
