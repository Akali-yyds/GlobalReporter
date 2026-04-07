"""
NewsSource model.
"""
from sqlalchemy import Boolean, Column, Integer, String

from app.models.base import BaseModel


class NewsSource(BaseModel):
    """News source model."""

    __tablename__ = "news_sources"

    name = Column(String(100), nullable=False, index=True)
    code = Column(String(50), nullable=False, unique=True, index=True)
    base_url = Column(String(500), nullable=False)
    country = Column(String(10), nullable=False, index=True)
    language = Column(String(10), nullable=False)
    category = Column(String(50), nullable=False)
    source_class = Column(String(20), nullable=False, default="news", index=True)
    source_tier = Column(String(20), nullable=False, default="authoritative", index=True)
    source_tier_level = Column(Integer, nullable=False, default=2, index=True)
    freshness_sla_hours = Column(Integer, nullable=False, default=24)
    license_mode = Column(String(30), nullable=False, default="public_web")
    is_active = Column(Boolean, default=True, nullable=False)
