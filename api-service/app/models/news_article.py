"""
NewsArticle model.
"""
import json
from sqlalchemy import Column, String, Integer, DateTime, Text
from sqlalchemy.types import TypeDecorator

from app.models.base import BaseModel


class JSONEncodedList(TypeDecorator):
    """Stores a list as JSON string for SQLite compatibility."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return json.dumps(value)
        return "[]"

    def process_result_value(self, value, dialect):
        if value is not None:
            return json.loads(value)
        return []


class NewsArticle(BaseModel):
    """News article model."""

    __tablename__ = "news_articles"

    title = Column(String(500), nullable=False, index=True)
    summary = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    article_url = Column(String(2000), nullable=False, unique=True, index=True)
    source_id = Column(String(36), nullable=False, index=True)
    source_name = Column(String(100), nullable=False)
    source_code = Column(String(50), nullable=False, index=True)
    source_url = Column(String(500), nullable=True)
    publish_time = Column(DateTime, nullable=True, index=True)
    crawl_time = Column(DateTime, nullable=False, index=True)
    heat_score = Column(Integer, default=0, index=True)
    category = Column(String(50), nullable=True, index=True)
    language = Column(String(10), nullable=False)
    country_tags = Column(JSONEncodedList, default=list)
    city_tags = Column(JSONEncodedList, default=list)
    region_tags = Column(JSONEncodedList, default=list)
    tags = Column(JSONEncodedList, default=list)
    hash = Column(String(64), nullable=False, unique=True, index=True)
