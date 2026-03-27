"""
EventGeoMapping model.
"""
from sqlalchemy import Column, String, Boolean, DECIMAL, ForeignKey

from app.models.base import BaseModel


class EventGeoMapping(BaseModel):
    """Mapping between events and geographic entities with extraction metadata."""

    __tablename__ = "event_geo_mappings"

    event_id = Column(String(36), ForeignKey("news_events.id"), nullable=False, index=True)
    geo_id = Column(String(36), ForeignKey("geo_entities.id"), nullable=False, index=True)
    geo_key = Column(String(20), nullable=False, index=True)
    
    # Extraction and analysis fields
    matched_text = Column(String(500), nullable=True)  # Original text that matched
    extraction_method = Column(String(50), nullable=True, index=True)  # dictionary_match|regex_match|fallback
    confidence = Column(DECIMAL(3, 2), default=1.0)  # 0.00 - 1.00
    relevance_score = Column(DECIMAL(3, 2), nullable=True, index=True)  # How relevant to the event
    is_primary = Column(Boolean, default=False, index=True)  # Is this the primary location for the event
    source_text_position = Column(String(20), nullable=True)  # title|summary|content
