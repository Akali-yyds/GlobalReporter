"""Per-source scheduled job profiles."""

from sqlalchemy import JSON, Boolean, Column, Integer, String, Text

from app.models.base import BaseModel


class SourceJobProfile(BaseModel):
    """Runtime job profile for realtime/backfill variants of a source."""

    __tablename__ = "source_job_profiles"

    job_name = Column(String(80), nullable=False, unique=True, index=True)
    source_code = Column(String(50), nullable=False, index=True)
    source_class = Column(String(20), nullable=False, default="event", index=True)
    job_mode = Column(String(20), nullable=False, default="realtime", index=True)
    window_mode = Column(String(20), nullable=False, default="relative")
    cursor_strategy = Column(String(40), nullable=False, default="none")
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    schedule_minutes = Column(Integer, nullable=False, default=60)
    priority = Column(Integer, nullable=False, default=0)
    default_params_json = Column(JSON, nullable=False, default=dict)
    notes = Column(Text, nullable=True)
