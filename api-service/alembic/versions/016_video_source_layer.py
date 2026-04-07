"""add video source layer

Revision ID: 016_video_source_layer
Revises: 015_feed_control_plane
Create Date: 2026-04-07
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "016_video_source_layer"
down_revision = "015_feed_control_plane"
branch_labels = None
depends_on = None


def _table_exists(bind, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _index_exists(bind, table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(bind)
    try:
      indexes = inspector.get_indexes(table_name)
    except Exception:
      return False
    return any(index.get("name") == index_name for index in indexes)


def upgrade() -> None:
    bind = op.get_bind()

    if not _table_exists(bind, "video_sources"):
        op.create_table(
        "video_sources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("source_code", sa.String(length=80), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("video_type", sa.String(length=40), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("channel_or_stream_id", sa.String(length=200), nullable=True),
        sa.Column("embed_url", sa.String(length=2000), nullable=True),
        sa.Column("playback_url", sa.String(length=2000), nullable=True),
        sa.Column("thumbnail_url", sa.String(length=2000), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("region", sa.String(length=120), nullable=True),
        sa.Column("country", sa.String(length=120), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("topic_tags", sa.JSON(), nullable=False),
        sa.Column("license_mode", sa.String(length=80), nullable=False, server_default="public_embed"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("rollout_state", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="unknown"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source_metadata", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_code"),
        )
    for index_name, columns in [
        ("ix_video_sources_source_code", ["source_code"]),
        ("ix_video_sources_video_type", ["video_type"]),
        ("ix_video_sources_provider", ["provider"]),
        ("ix_video_sources_region", ["region"]),
        ("ix_video_sources_country", ["country"]),
        ("ix_video_sources_city", ["city"]),
        ("ix_video_sources_priority", ["priority"]),
        ("ix_video_sources_enabled", ["enabled"]),
        ("ix_video_sources_rollout_state", ["rollout_state"]),
        ("ix_video_sources_status", ["status"]),
    ]:
        if not _index_exists(bind, "video_sources", index_name):
            op.create_index(index_name, "video_sources", columns)

    if not _table_exists(bind, "video_job_checkpoints"):
        op.create_table(
        "video_job_checkpoints",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("source_code", sa.String(length=80), nullable=False),
        sa.Column("job_code", sa.String(length=80), nullable=False),
        sa.Column("last_probe_at", sa.DateTime(), nullable=True),
        sa.Column("last_success_at", sa.DateTime(), nullable=True),
        sa.Column("last_http_status", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("is_live", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_title", sa.String(length=500), nullable=True),
        sa.Column("last_thumbnail", sa.String(length=2000), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_code", "job_code", name="uq_video_job_checkpoint_source_job"),
        )
    for index_name, columns in [
        ("ix_video_job_checkpoints_source_code", ["source_code"]),
        ("ix_video_job_checkpoints_job_code", ["job_code"]),
        ("ix_video_job_checkpoints_last_probe_at", ["last_probe_at"]),
        ("ix_video_job_checkpoints_last_success_at", ["last_success_at"]),
        ("ix_video_job_checkpoints_is_live", ["is_live"]),
    ]:
        if not _index_exists(bind, "video_job_checkpoints", index_name):
            op.create_index(index_name, "video_job_checkpoints", columns)

    if not _table_exists(bind, "video_job_profiles"):
        op.create_table(
        "video_job_profiles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("job_code", sa.String(length=80), nullable=False),
        sa.Column("job_mode", sa.String(length=20), nullable=False, server_default="realtime"),
        sa.Column("rollout_state", sa.String(length=20), nullable=False, server_default="default"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("interval_minutes", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("max_sources", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_code", name="uq_video_job_profiles_job_code"),
        )
    for index_name, columns in [
        ("ix_video_job_profiles_job_code", ["job_code"]),
        ("ix_video_job_profiles_job_mode", ["job_mode"]),
        ("ix_video_job_profiles_rollout_state", ["rollout_state"]),
        ("ix_video_job_profiles_enabled", ["enabled"]),
    ]:
        if not _index_exists(bind, "video_job_profiles", index_name):
            op.create_index(index_name, "video_job_profiles", columns)


def downgrade() -> None:
    op.drop_index("ix_video_job_profiles_enabled", table_name="video_job_profiles")
    op.drop_index("ix_video_job_profiles_rollout_state", table_name="video_job_profiles")
    op.drop_index("ix_video_job_profiles_job_mode", table_name="video_job_profiles")
    op.drop_index("ix_video_job_profiles_job_code", table_name="video_job_profiles")
    op.drop_table("video_job_profiles")

    op.drop_index("ix_video_job_checkpoints_is_live", table_name="video_job_checkpoints")
    op.drop_index("ix_video_job_checkpoints_last_success_at", table_name="video_job_checkpoints")
    op.drop_index("ix_video_job_checkpoints_last_probe_at", table_name="video_job_checkpoints")
    op.drop_index("ix_video_job_checkpoints_job_code", table_name="video_job_checkpoints")
    op.drop_index("ix_video_job_checkpoints_source_code", table_name="video_job_checkpoints")
    op.drop_table("video_job_checkpoints")

    op.drop_index("ix_video_sources_status", table_name="video_sources")
    op.drop_index("ix_video_sources_rollout_state", table_name="video_sources")
    op.drop_index("ix_video_sources_enabled", table_name="video_sources")
    op.drop_index("ix_video_sources_priority", table_name="video_sources")
    op.drop_index("ix_video_sources_city", table_name="video_sources")
    op.drop_index("ix_video_sources_country", table_name="video_sources")
    op.drop_index("ix_video_sources_region", table_name="video_sources")
    op.drop_index("ix_video_sources_provider", table_name="video_sources")
    op.drop_index("ix_video_sources_video_type", table_name="video_sources")
    op.drop_index("ix_video_sources_source_code", table_name="video_sources")
    op.drop_table("video_sources")
