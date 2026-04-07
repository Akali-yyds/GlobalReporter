"""Feed-level source profiles."""

from sqlalchemy import Boolean, Column, Integer, String, Text, UniqueConstraint

from app.models.base import BaseModel


class SourceFeedProfile(BaseModel):
    """Per-feed rollout and freshness controls for a source."""

    __tablename__ = "source_feed_profiles"
    __table_args__ = (
        UniqueConstraint("source_code", "feed_code", name="uq_source_feed_profiles_source_feed"),
    )

    source_code = Column(String(50), nullable=False, index=True)
    feed_code = Column(String(80), nullable=False, index=True)
    feed_url = Column(String(2000), nullable=False)
    feed_name = Column(String(120), nullable=False)
    priority = Column(Integer, nullable=False, default=100, index=True)
    freshness_sla_hours = Column(Integer, nullable=False, default=24)
    rollout_state = Column(String(20), nullable=False, default="default", index=True)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    expected_update_interval_hours = Column(Integer, nullable=False, default=24)
    license_mode = Column(String(40), nullable=False, default="public_web")
    notes = Column(Text, nullable=True)
