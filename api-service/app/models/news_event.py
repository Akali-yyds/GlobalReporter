"""
NewsEvent model.
"""
from sqlalchemy import Column, String, Integer, DateTime, Text

from app.models.base import BaseModel


class NewsEvent(BaseModel):
    """News event model - aggregated from multiple articles."""

    __tablename__ = "news_events"

    title = Column(String(500), nullable=False, index=True)
    summary = Column(Text, nullable=True)
    main_country = Column(String(10), nullable=False, index=True)
    event_level = Column(String(20), nullable=False, default="country")  # country/city/region
    heat_score = Column(Integer, default=0, index=True)
    article_count = Column(Integer, default=0)
    category = Column(String(50), nullable=True, index=True)
    title_hash = Column(String(64), nullable=False, unique=True, index=True)
    first_seen_at = Column(DateTime, nullable=False)
    last_seen_at = Column(DateTime, nullable=False)
