"""Payload for crawler → API ingestion."""
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class CrawledGeoEntityIngest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=1)
    geo_key: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    confidence: float = 1.0
    country_code: Optional[str] = None
    country_name: Optional[str] = None
    admin1_code: Optional[str] = None
    admin1_name: Optional[str] = None
    city_name: Optional[str] = None
    precision_level: Optional[str] = None
    display_mode: Optional[str] = None
    geojson_key: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    matched_text: Optional[str] = None
    source_text_position: Optional[str] = None
    relevance_score: Optional[float] = None


class CrawledArticleIngest(BaseModel):
    """One article from Scrapy pipeline."""

    model_config = ConfigDict(populate_by_name=True)

    title: str = Field(..., min_length=1)
    summary: Optional[str] = None
    content: Optional[str] = None
    url: str = Field(..., min_length=4, description="Article URL (maps to article_url)")
    source_name: str
    source_code: str
    source_url: Optional[str] = None
    language: str = "zh"
    country: str = "CN"
    category: Optional[str] = None
    heat_score: int = 0
    content_hash: str = Field(..., min_length=8, alias="hash")
    published_at: Optional[Any] = None
    crawled_at: Optional[Any] = None
    tags: Optional[List[str]] = None
    region_tags: Optional[List[str]] = None
    geo_entities: Optional[List[CrawledGeoEntityIngest]] = None
