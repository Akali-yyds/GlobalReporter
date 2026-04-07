"""add job profiles and geometry persistence

Revision ID: 008_job_profiles
Revises: 007_event_lifecycle
Create Date: 2026-04-06
"""

from alembic import op
import sqlalchemy as sa


revision = "008_job_profiles"
down_revision = "007_event_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("news_articles") as batch_op:
        batch_op.add_column(sa.Column("geom_type", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("raw_geometry", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("display_geo", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("bbox", sa.JSON(), nullable=True))
        batch_op.create_index("ix_news_articles_geom_type", ["geom_type"], unique=False)

    with op.batch_alter_table("news_events") as batch_op:
        batch_op.add_column(sa.Column("geom_type", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("raw_geometry", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("display_geo", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("bbox", sa.JSON(), nullable=True))
        batch_op.create_index("ix_news_events_geom_type", ["geom_type"], unique=False)

    op.create_table(
        "source_job_profiles",
        sa.Column("job_name", sa.String(length=80), nullable=False),
        sa.Column("source_code", sa.String(length=50), nullable=False),
        sa.Column("source_class", sa.String(length=20), nullable=False),
        sa.Column("job_mode", sa.String(length=20), nullable=False),
        sa.Column("window_mode", sa.String(length=20), nullable=False),
        sa.Column("cursor_strategy", sa.String(length=40), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("schedule_minutes", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("default_params_json", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_source_job_profiles_job_name", "source_job_profiles", ["job_name"], unique=True)
    op.create_index("ix_source_job_profiles_source_code", "source_job_profiles", ["source_code"], unique=False)
    op.create_index("ix_source_job_profiles_job_mode", "source_job_profiles", ["job_mode"], unique=False)
    op.create_index("ix_source_job_profiles_enabled", "source_job_profiles", ["enabled"], unique=False)

    op.create_table(
        "source_job_checkpoints",
        sa.Column("job_name", sa.String(length=80), nullable=False),
        sa.Column("source_code", sa.String(length=50), nullable=False),
        sa.Column("job_mode", sa.String(length=20), nullable=False),
        sa.Column("last_success_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen_external_id", sa.String(length=255), nullable=True),
        sa.Column("last_seen_source_updated_at", sa.DateTime(), nullable=True),
        sa.Column("last_event_time", sa.DateTime(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_source_job_checkpoints_job_name", "source_job_checkpoints", ["job_name"], unique=True)
    op.create_index("ix_source_job_checkpoints_source_code", "source_job_checkpoints", ["source_code"], unique=False)
    op.create_index("ix_source_job_checkpoints_job_mode", "source_job_checkpoints", ["job_mode"], unique=False)
    op.create_index("ix_source_job_checkpoints_last_success_at", "source_job_checkpoints", ["last_success_at"], unique=False)
    op.create_index(
        "ix_source_job_checkpoints_last_seen_source_updated_at",
        "source_job_checkpoints",
        ["last_seen_source_updated_at"],
        unique=False,
    )
    op.create_index("ix_source_job_checkpoints_last_event_time", "source_job_checkpoints", ["last_event_time"], unique=False)

    conn = op.get_bind()
    json_type = "jsonb" if conn.dialect.name == "postgresql" else "json"

    def insert_job_profile(
        *,
        profile_id: str,
        job_name: str,
        source_code: str,
        job_mode: str,
        window_mode: str,
        cursor_strategy: str,
        schedule_minutes: int,
        priority: int,
        payload: str,
        notes: str,
    ) -> None:
        op.execute(
            sa.text(
                f"""
                INSERT INTO source_job_profiles (
                    id, job_name, source_code, source_class, job_mode, window_mode, cursor_strategy,
                    enabled, schedule_minutes, priority, default_params_json, notes, created_at, updated_at
                ) VALUES (
                    :id, :job_name, :source_code, 'event', :job_mode, :window_mode, :cursor_strategy,
                    TRUE, :schedule_minutes, :priority, CAST(:payload AS {json_type}), :notes,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """
            ).bindparams(
                id=profile_id,
                job_name=job_name,
                source_code=source_code,
                job_mode=job_mode,
                window_mode=window_mode,
                cursor_strategy=cursor_strategy,
                schedule_minutes=schedule_minutes,
                priority=priority,
                payload=payload,
                notes=notes,
            )
        )

    insert_job_profile(
        profile_id="job-earthquake-usgs-rt",
        job_name="earthquake_usgs_realtime",
        source_code="earthquake_usgs",
        job_mode="realtime",
        window_mode="relative",
        cursor_strategy="last_seen_source_updated_at",
        schedule_minutes=5,
        priority=9,
        payload='{"feeds":["significant_hour","all_hour","significant_day","all_day"]}',
        notes="Small-window realtime USGS polling.",
    )
    insert_job_profile(
        profile_id="job-earthquake-usgs-bf",
        job_name="earthquake_usgs_backfill",
        source_code="earthquake_usgs",
        job_mode="backfill",
        window_mode="relative",
        cursor_strategy="last_seen_source_updated_at",
        schedule_minutes=240,
        priority=4,
        payload='{"feeds":["all_day","all_week"],"replay_window_days":7}',
        notes="Low-frequency USGS backfill/recovery pass.",
    )
    insert_job_profile(
        profile_id="job-eonet-events-rt",
        job_name="eonet_events_realtime",
        source_code="eonet_events",
        job_mode="realtime",
        window_mode="relative",
        cursor_strategy="last_seen_source_updated_at",
        schedule_minutes=30,
        priority=8,
        payload='{"status":"open","category":["wildfires","severeStorms","volcanoes"],"days":7,"limit":500}',
        notes="Realtime EONET open-event polling.",
    )
    insert_job_profile(
        profile_id="job-eonet-events-bf",
        job_name="eonet_events_backfill",
        source_code="eonet_events",
        job_mode="backfill",
        window_mode="absolute",
        cursor_strategy="last_seen_source_updated_at",
        schedule_minutes=360,
        priority=4,
        payload='{"status":"all","category":["wildfires","severeStorms","volcanoes"],"days":30,"limit":500}',
        notes="EONET backfill/history repair job.",
    )


def downgrade() -> None:
    op.drop_index("ix_source_job_checkpoints_last_event_time", table_name="source_job_checkpoints")
    op.drop_index("ix_source_job_checkpoints_last_seen_source_updated_at", table_name="source_job_checkpoints")
    op.drop_index("ix_source_job_checkpoints_last_success_at", table_name="source_job_checkpoints")
    op.drop_index("ix_source_job_checkpoints_job_mode", table_name="source_job_checkpoints")
    op.drop_index("ix_source_job_checkpoints_source_code", table_name="source_job_checkpoints")
    op.drop_index("ix_source_job_checkpoints_job_name", table_name="source_job_checkpoints")
    op.drop_table("source_job_checkpoints")

    op.drop_index("ix_source_job_profiles_enabled", table_name="source_job_profiles")
    op.drop_index("ix_source_job_profiles_job_mode", table_name="source_job_profiles")
    op.drop_index("ix_source_job_profiles_source_code", table_name="source_job_profiles")
    op.drop_index("ix_source_job_profiles_job_name", table_name="source_job_profiles")
    op.drop_table("source_job_profiles")

    with op.batch_alter_table("news_events") as batch_op:
        batch_op.drop_index("ix_news_events_geom_type")
        batch_op.drop_column("bbox")
        batch_op.drop_column("display_geo")
        batch_op.drop_column("raw_geometry")
        batch_op.drop_column("geom_type")

    with op.batch_alter_table("news_articles") as batch_op:
        batch_op.drop_index("ix_news_articles_geom_type")
        batch_op.drop_column("bbox")
        batch_op.drop_column("display_geo")
        batch_op.drop_column("raw_geometry")
        batch_op.drop_column("geom_type")
