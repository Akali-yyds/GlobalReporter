"""
NewsSource model.
"""
from sqlalchemy import Column, String, Boolean

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
    source_tier = Column(String(20), nullable=False, default="authoritative", index=True)
    is_active = Column(Boolean, default=True, nullable=False)
