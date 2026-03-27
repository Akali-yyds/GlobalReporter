"""
CrawlJob model.
"""
from sqlalchemy import Column, String, Integer, DateTime

from app.models.base import BaseModel


class CrawlJob(BaseModel):
    """Crawl job model."""

    __tablename__ = "crawl_jobs"

    source_id = Column(String(36), nullable=False, index=True)
    spider_name = Column(String(100), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="pending")  # pending/running/completed/failed
    items_crawled = Column(Integer, default=0)
    items_processed = Column(Integer, default=0)
    error_message = Column(String(2000), nullable=True)
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)
