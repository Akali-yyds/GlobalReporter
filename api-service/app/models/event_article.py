"""
EventArticle association model.
"""
from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class EventArticle(BaseModel):
    """Association between events and articles."""

    __tablename__ = "event_articles"

    event_id = Column(String(36), ForeignKey("news_events.id"), nullable=False, index=True)
    article_id = Column(String(36), ForeignKey("news_articles.id"), nullable=False, index=True)
    is_primary = Column(Boolean, default=False)
