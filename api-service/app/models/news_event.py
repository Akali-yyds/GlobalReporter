"""
NewsEvent model.
"""
from sqlalchemy import JSON, Column, DateTime, Index, Integer, String, Text, UniqueConstraint

from app.models.base import BaseModel
from app.models.news_article import JSONEncodedList


class NewsEvent(BaseModel):
    """News event model - aggregated from multiple articles."""

    __tablename__ = "news_events"
    __table_args__ = (
        UniqueConstraint("source_code", "external_id", name="uq_news_events_source_external"),
        Index("ix_news_events_source_code_event_time", "source_code", "event_time"),
        Index("ix_news_events_event_status_event_time", "event_status", "event_time"),
    )

    title = Column(String(500), nullable=False, index=True)
    summary = Column(Text, nullable=True)
    main_country = Column(String(10), nullable=False, index=True)
    event_level = Column(String(20), nullable=False, default="country")  # country/city/region
    source_code = Column(String(50), nullable=True, index=True)
    source_class = Column(String(20), nullable=False, default="news", index=True)
    heat_score = Column(Integer, default=0, index=True)
    severity = Column(Integer, default=0, index=True)
    confidence = Column(Integer, default=100, nullable=False)
    article_count = Column(Integer, default=0)
    category = Column(String(50), nullable=True, index=True)
    geo = Column(String(20), nullable=True, index=True)
    geom_type = Column(String(20), nullable=True, index=True)
    raw_geometry = Column(JSON, nullable=True)
    display_geo = Column(JSON, nullable=True)
    bbox = Column(JSON, nullable=True)
    source_metadata = Column(JSON, nullable=True)
    tags = Column(JSONEncodedList, default=list)
    source_tier = Column(String(20), nullable=False, default="authoritative", index=True)
    source_tier_level = Column(Integer, nullable=False, default=2, index=True)
    freshness_sla_hours = Column(Integer, nullable=False, default=24)
    event_time = Column(DateTime, nullable=True, index=True)
    event_status = Column(String(20), nullable=False, default="closed", index=True)
    closed_at = Column(DateTime, nullable=True)
    source_updated_at = Column(DateTime, nullable=True, index=True)
    license_mode = Column(String(30), nullable=False, default="public_web")
    canonical_url = Column(String(2000), nullable=True, index=True)
    external_id = Column(String(255), nullable=True, index=True)
    title_hash = Column(String(64), nullable=False, unique=True, index=True)
    first_seen_at = Column(DateTime, nullable=False)
    last_seen_at = Column(DateTime, nullable=False)
