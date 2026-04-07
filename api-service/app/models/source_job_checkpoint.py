"""Checkpoint state for source job profiles."""

from sqlalchemy import JSON, Column, DateTime, Integer, String

from app.models.base import BaseModel


class SourceJobCheckpoint(BaseModel):
    """Stores last successful cursor/checkpoint for a source job."""

    __tablename__ = "source_job_checkpoints"

    job_name = Column(String(80), nullable=False, unique=True, index=True)
    source_code = Column(String(50), nullable=False, index=True)
    job_mode = Column(String(20), nullable=False, default="realtime", index=True)
    last_success_at = Column(DateTime, nullable=True, index=True)
    last_seen_external_id = Column(String(255), nullable=True)
    last_seen_source_updated_at = Column(DateTime, nullable=True, index=True)
    last_event_time = Column(DateTime, nullable=True, index=True)
    last_seen_page = Column(Integer, nullable=True)
    last_query_window = Column(JSON, nullable=True)
