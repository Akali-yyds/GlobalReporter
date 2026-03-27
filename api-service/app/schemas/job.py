"""Crawl job API schemas."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class CrawlJobResponse(BaseModel):
    """Serialized crawl job for JSON responses."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    source_id: str
    spider_name: str
    status: str
    items_crawled: int
    items_processed: int
    error_message: Optional[str] = None
    started_at: datetime
    finished_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class CrawlTriggerBody(BaseModel):
    """Manual crawl: item budget + optional multi-spider scope."""

    max_items: int = Field(50, ge=5, le=500, description="Target items per run (split across spiders when scope is set)")
    crawl_scope: Optional[Literal["china", "world", "all"]] = Field(
        None,
        description="Run domestic / international / both spider sets; omit for single-spider mode",
    )
    spider: Optional[str] = Field(None, description="Single spider name when crawl_scope is omitted")
