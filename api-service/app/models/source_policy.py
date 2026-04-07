"""Per-source ingestion strategy overrides."""

from sqlalchemy import JSON, Boolean, Column, Integer, String, Text

from app.models.base import BaseModel


class SourcePolicy(BaseModel):
    """Configurable strategy row that overrides static source defaults."""

    __tablename__ = "source_policies"

    source_code = Column(String(50), nullable=False, unique=True, index=True)
    source_class = Column(String(20), nullable=False, default="news", index=True)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    fetch_mode = Column(String(20), nullable=False, default="poll_feed")
    schedule_minutes = Column(Integer, nullable=False, default=60)
    freshness_sla_hours = Column(Integer, nullable=False, default=24)
    dedup_key_mode = Column(String(30), nullable=False, default="canonical_url")
    event_time_field_priority = Column(JSON, nullable=False, default=list)
    severity_mapping_rule = Column(String(50), nullable=True)
    geo_precision_rule = Column(String(50), nullable=True)
    default_params_json = Column(JSON, nullable=False, default=dict)
    license_mode = Column(String(30), nullable=False, default="public_web")
    notes = Column(Text, nullable=True)
