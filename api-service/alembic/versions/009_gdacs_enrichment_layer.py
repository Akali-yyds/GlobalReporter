"""add gdacs enrichment metadata and job profiles

Revision ID: 009_gdacs_enrichment
Revises: 008_job_profiles
Create Date: 2026-04-06
"""

from alembic import op
import sqlalchemy as sa


revision = "009_gdacs_enrichment"
down_revision = "008_job_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("news_articles") as batch_op:
        batch_op.add_column(sa.Column("source_metadata", sa.JSON(), nullable=True))

    with op.batch_alter_table("news_events") as batch_op:
        batch_op.add_column(sa.Column("source_metadata", sa.JSON(), nullable=True))

    with op.batch_alter_table("source_job_checkpoints") as batch_op:
        batch_op.add_column(sa.Column("last_seen_page", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("last_query_window", sa.JSON(), nullable=True))

    conn = op.get_bind()
    json_type = "jsonb" if conn.dialect.name == "postgresql" else "json"

    op.execute(
        sa.text(
            f"""
            UPDATE source_policies
            SET fetch_mode = 'poll_api',
                schedule_minutes = 10,
                freshness_sla_hours = 72,
                dedup_key_mode = 'external_id',
                event_time_field_priority = CAST(:priority AS {json_type}),
                severity_mapping_rule = 'gdacs_alert_level',
                geo_precision_rule = 'keep_raw_geometry_then_display_geo',
                default_params_json = CAST(:params AS {json_type}),
                license_mode = 'attribution_required',
                notes = 'GDACS alert/enrichment layer via API SEARCH.'
            WHERE source_code = 'disaster_gdacs'
            """
        ).bindparams(
            priority='["source_updated_at","event_time","published_at"]',
            params=(
                '{"realtime":{"event_types":["EQ","FL","TC"],"relative_days":7,'
                '"pagesize":100,"max_pages":4,"alert_levels":["orange","red"]},'
                '"backfill":{"event_types":["EQ","FL","TC"],"relative_days":7,'
                '"pagesize":100,"max_pages":12,"alert_levels":["green","orange","red"]}}'
            ),
        )
    )

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
        profile_id="job-disaster-gdacs-rt",
        job_name="disaster_gdacs_realtime",
        source_code="disaster_gdacs",
        job_mode="realtime",
        window_mode="relative",
        cursor_strategy="last_seen_source_updated_at",
        schedule_minutes=10,
        priority=8,
        payload='{"event_types":["EQ","FL","TC"],"relative_days":7,"pagesize":100,"max_pages":4,"alert_levels":["orange","red"]}',
        notes="Realtime GDACS alert enrichment polling.",
    )
    insert_job_profile(
        profile_id="job-disaster-gdacs-bf",
        job_name="disaster_gdacs_backfill",
        source_code="disaster_gdacs",
        job_mode="backfill",
        window_mode="relative",
        cursor_strategy="last_seen_source_updated_at",
        schedule_minutes=1440,
        priority=3,
        payload='{"event_types":["EQ","FL","TC"],"relative_days":7,"pagesize":100,"max_pages":12,"alert_levels":["green","orange","red"]}',
        notes="Low-frequency GDACS backfill and enrichment repair job.",
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM source_job_profiles
            WHERE job_name IN ('disaster_gdacs_realtime', 'disaster_gdacs_backfill')
            """
        )
    )

    conn = op.get_bind()
    json_type = "jsonb" if conn.dialect.name == "postgresql" else "json"
    op.execute(
        sa.text(
            f"""
            UPDATE source_policies
            SET fetch_mode = 'poll_feed',
                schedule_minutes = 30,
                freshness_sla_hours = 72,
                dedup_key_mode = 'external_id',
                event_time_field_priority = CAST(:priority AS {json_type}),
                severity_mapping_rule = 'gdacs_alert_level',
                geo_precision_rule = 'geometry',
                default_params_json = CAST(:params AS {json_type}),
                license_mode = 'event_feed',
                notes = 'GDACS alert enrichment layer.'
            WHERE source_code = 'disaster_gdacs'
            """
        ).bindparams(
            priority='["event_time","published_at"]',
            params='{"alert_levels":["orange","red"]}',
        )
    )

    with op.batch_alter_table("source_job_checkpoints") as batch_op:
        batch_op.drop_column("last_query_window")
        batch_op.drop_column("last_seen_page")

    with op.batch_alter_table("news_events") as batch_op:
        batch_op.drop_column("source_metadata")

    with op.batch_alter_table("news_articles") as batch_op:
        batch_op.drop_column("source_metadata")
