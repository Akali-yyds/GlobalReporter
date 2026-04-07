"""Feed-level crawler health snapshots."""

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, UniqueConstraint

from app.models.base import BaseModel


class SourceFeedHealth(BaseModel):
    """Aggregated near-real-time health metrics for a source feed."""

    __tablename__ = "source_feed_health"
    __table_args__ = (
        UniqueConstraint("source_code", "feed_code", name="uq_source_feed_health_source_feed"),
    )

    source_code = Column(String(50), nullable=False, index=True)
    feed_code = Column(String(80), nullable=False, index=True)
    feed_profile_id = Column(String(36), nullable=True, index=True)
    last_fetch_at = Column(DateTime, nullable=True, index=True)
    last_success_at = Column(DateTime, nullable=True, index=True)
    last_fresh_item_at = Column(DateTime, nullable=True, index=True)
    last_http_status = Column(Integer, nullable=True)
    last_error = Column(Text, nullable=True)
    scraped_count_24h = Column(Integer, nullable=False, default=0)
    dropped_stale_count_24h = Column(Integer, nullable=False, default=0)
    dropped_quality_count_24h = Column(Integer, nullable=False, default=0)
    stale_ratio_24h = Column(Float, nullable=False, default=0.0)
    direct_ok_rate_24h = Column(Float, nullable=False, default=0.0)
    consecutive_failures = Column(Integer, nullable=False, default=0)
    direct_attempt_count_24h = Column(Integer, nullable=False, default=0)
    direct_ok_count_24h = Column(Integer, nullable=False, default=0)
    window_started_at = Column(DateTime, nullable=True, index=True)
