"""
News schema definitions.
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class NewsArticleBase(BaseModel):
    """Base news article schema."""
    title: str
    summary: Optional[str] = None
    content: Optional[str] = None
    article_url: str
    source_name: str
    source_code: str
    source_class: str = "news"
    publish_time: Optional[datetime] = None
    event_time: Optional[datetime] = None
    freshness_sla_hours: int = 24
    heat_score: int = 0
    severity: int = 0
    confidence: int = 100
    category: Optional[str] = None
    language: str = "zh"
    geo: Optional[str] = None
    license_mode: str = "public_web"
    canonical_url: Optional[str] = None
    external_id: Optional[str] = None


class NewsArticleCreate(NewsArticleBase):
    """Schema for creating a news article."""
    source_id: str
    source_url: Optional[str] = None
    crawl_time: datetime
    country_tags: List[str] = []
    city_tags: List[str] = []
    tags: List[str] = []
    hash: str


class NewsArticleResponse(NewsArticleBase):
    """Schema for news article response."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_id: str
    source_url: Optional[str] = None
    crawl_time: datetime
    country_tags: List[str] = []
    city_tags: List[str] = []
    region_tags: List[str] = []
    tags: List[str] = []
    hash: str
    created_at: datetime
    updated_at: datetime


class NewsArticleListResponse(BaseModel):
    """Schema for news article list response."""
    total: int
    page: int
    page_size: int
    items: List[NewsArticleResponse]
