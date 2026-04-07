"""Video probe checkpoint and health state."""

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, UniqueConstraint

from app.models.base import BaseModel


class VideoJobCheckpoint(BaseModel):
    """Checkpoint for a video probe job against a source."""

    __tablename__ = "video_job_checkpoints"
    __table_args__ = (
        UniqueConstraint("source_code", "job_code", name="uq_video_job_checkpoint_source_job"),
    )

    source_code = Column(String(80), nullable=False, index=True)
    job_code = Column(String(80), nullable=False, index=True)
    last_probe_at = Column(DateTime, nullable=True, index=True)
    last_success_at = Column(DateTime, nullable=True, index=True)
    last_http_status = Column(Integer, nullable=True)
    last_error = Column(Text, nullable=True)
    is_live = Column(Boolean, nullable=False, default=False, index=True)
    last_title = Column(String(500), nullable=True)
    last_thumbnail = Column(String(2000), nullable=True)
    consecutive_failures = Column(Integer, nullable=False, default=0)
