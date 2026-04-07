"""Video source model."""

from sqlalchemy import Boolean, Column, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON
from sqlalchemy.types import JSON

from app.models.base import BaseModel


JSONType = JSON().with_variant(SQLITE_JSON, "sqlite")


class VideoSource(BaseModel):
    """Embeddable or directly playable live video source."""

    __tablename__ = "video_sources"

    source_code = Column(String(80), nullable=False, unique=True, index=True)
    display_name = Column(String(200), nullable=False)
    video_type = Column(String(40), nullable=False, index=True)
    provider = Column(String(40), nullable=False, index=True)
    channel_or_stream_id = Column(String(200), nullable=True)
    embed_url = Column(String(2000), nullable=True)
    playback_url = Column(String(2000), nullable=True)
    thumbnail_url = Column(String(2000), nullable=True)
    title = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    region = Column(String(120), nullable=True, index=True)
    country = Column(String(120), nullable=True, index=True)
    city = Column(String(120), nullable=True, index=True)
    topic_tags = Column(JSONType, nullable=False, default=list)
    license_mode = Column(String(80), nullable=False, default="public_embed")
    priority = Column(Integer, nullable=False, default=100, index=True)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    rollout_state = Column(String(20), nullable=False, default="draft", index=True)
    status = Column(String(20), nullable=False, default="unknown", index=True)
    notes = Column(Text, nullable=True)
    source_metadata = Column(JSONType, nullable=False, default=dict)
