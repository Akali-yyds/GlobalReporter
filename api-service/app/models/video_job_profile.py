"""Video probe scheduling profile."""

from sqlalchemy import Boolean, Column, Integer, String, Text, UniqueConstraint

from app.models.base import BaseModel


class VideoJobProfile(BaseModel):
    """Defines how a video probe job should be scheduled."""

    __tablename__ = "video_job_profiles"
    __table_args__ = (
        UniqueConstraint("job_code", name="uq_video_job_profiles_job_code"),
    )

    job_code = Column(String(80), nullable=False, index=True)
    job_mode = Column(String(20), nullable=False, default="realtime", index=True)
    rollout_state = Column(String(20), nullable=False, default="default", index=True)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    interval_minutes = Column(Integer, nullable=False, default=15)
    max_sources = Column(Integer, nullable=False, default=20)
    notes = Column(Text, nullable=True)
