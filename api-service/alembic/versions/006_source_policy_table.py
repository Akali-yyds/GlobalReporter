"""add source policy table

Revision ID: 006_source_policy
Revises: 005_source_class_meta
Create Date: 2026-04-06
"""

from alembic import op
import sqlalchemy as sa


revision = "006_source_policy"
down_revision = "005_source_class_meta"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_policies",
        sa.Column("source_code", sa.String(length=50), nullable=False),
        sa.Column("source_class", sa.String(length=20), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("fetch_mode", sa.String(length=20), nullable=False),
        sa.Column("schedule_minutes", sa.Integer(), nullable=False),
        sa.Column("freshness_sla_hours", sa.Integer(), nullable=False),
        sa.Column("dedup_key_mode", sa.String(length=30), nullable=False),
        sa.Column("event_time_field_priority", sa.JSON(), nullable=False),
        sa.Column("severity_mapping_rule", sa.String(length=50), nullable=True),
        sa.Column("geo_precision_rule", sa.String(length=50), nullable=True),
        sa.Column("default_params_json", sa.JSON(), nullable=False),
        sa.Column("license_mode", sa.String(length=30), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_source_policies_source_code", "source_policies", ["source_code"], unique=True)
    op.create_index("ix_source_policies_source_class", "source_policies", ["source_class"], unique=False)
    op.create_index("ix_source_policies_enabled", "source_policies", ["enabled"], unique=False)

    conn = op.get_bind()
    is_postgres = conn.dialect.name == "postgresql"
    json_type = "jsonb" if is_postgres else "json"

    def insert_policy(
        *,
        policy_id: str,
        source_code: str,
        source_class: str,
        enabled: bool,
        fetch_mode: str,
        schedule_minutes: int,
        freshness_sla_hours: int,
        dedup_key_mode: str,
        event_time_field_priority: str,
        severity_mapping_rule: str | None,
        geo_precision_rule: str | None,
        default_params_json: str,
        license_mode: str,
        notes: str,
    ) -> None:
        op.execute(
            sa.text(
                f"""
                INSERT INTO source_policies (
                    id, source_code, source_class, enabled, fetch_mode, schedule_minutes,
                    freshness_sla_hours, dedup_key_mode, event_time_field_priority,
                    severity_mapping_rule, geo_precision_rule, default_params_json,
                    license_mode, notes, created_at, updated_at
                ) VALUES (
                    :id, :source_code, :source_class, :enabled, :fetch_mode, :schedule_minutes,
                    :freshness_sla_hours, :dedup_key_mode,
                    CAST(:event_time_field_priority AS {json_type}),
                    :severity_mapping_rule, :geo_precision_rule,
                    CAST(:default_params_json AS {json_type}),
                    :license_mode, :notes, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """
            ).bindparams(
                id=policy_id,
                source_code=source_code,
                source_class=source_class,
                enabled=enabled,
                fetch_mode=fetch_mode,
                schedule_minutes=schedule_minutes,
                freshness_sla_hours=freshness_sla_hours,
                dedup_key_mode=dedup_key_mode,
                event_time_field_priority=event_time_field_priority,
                severity_mapping_rule=severity_mapping_rule,
                geo_precision_rule=geo_precision_rule,
                default_params_json=default_params_json,
                license_mode=license_mode,
                notes=notes,
            )
        )

    insert_policy(
        policy_id="policy-openai-official",
        source_code="openai_official",
        source_class="lead",
        enabled=True,
        fetch_mode="poll_feed",
        schedule_minutes=360,
        freshness_sla_hours=168,
        dedup_key_mode="canonical_url",
        event_time_field_priority='["published_at"]',
        severity_mapping_rule=None,
        geo_precision_rule="text_geo",
        default_params_json="{}",
        license_mode="official_public",
        notes="Official product/news feed with longer SLA.",
    )
    insert_policy(
        policy_id="policy-youtube-official",
        source_code="youtube_official",
        source_class="lead",
        enabled=True,
        fetch_mode="poll_feed",
        schedule_minutes=180,
        freshness_sla_hours=48,
        dedup_key_mode="canonical_url",
        event_time_field_priority='["published_at"]',
        severity_mapping_rule=None,
        geo_precision_rule="text_geo",
        default_params_json="{}",
        license_mode="official_public",
        notes="Official video feed with short lead-style SLA.",
    )
    insert_policy(
        policy_id="policy-github-changelog",
        source_code="github_changelog",
        source_class="lead",
        enabled=True,
        fetch_mode="poll_feed",
        schedule_minutes=360,
        freshness_sla_hours=168,
        dedup_key_mode="canonical_url",
        event_time_field_priority='["published_at"]',
        severity_mapping_rule=None,
        geo_precision_rule="text_geo",
        default_params_json="{}",
        license_mode="community_public",
        notes="Community changelog / product update feed.",
    )
    insert_policy(
        policy_id="policy-earthquake-usgs",
        source_code="earthquake_usgs",
        source_class="event",
        enabled=True,
        fetch_mode="poll_feed",
        schedule_minutes=15,
        freshness_sla_hours=48,
        dedup_key_mode="external_id",
        event_time_field_priority='["event_time","published_at"]',
        severity_mapping_rule="usgs_magnitude",
        geo_precision_rule="point",
        default_params_json='{"feeds":["all_hour","all_day","significant_hour","significant_day"]}',
        license_mode="event_feed",
        notes="USGS realtime GeoJSON earthquake feeds.",
    )
    insert_policy(
        policy_id="policy-eonet-events",
        source_code="eonet_events",
        source_class="event",
        enabled=True,
        fetch_mode="poll_api",
        schedule_minutes=60,
        freshness_sla_hours=168,
        dedup_key_mode="external_id",
        event_time_field_priority='["event_time","published_at"]',
        severity_mapping_rule="eonet_category",
        geo_precision_rule="geometry",
        default_params_json='{"status":"open","days":7,"categories":["wildfires","severeStorms","volcanoes","floods"]}',
        license_mode="event_feed",
        notes="NASA EONET open events polling strategy.",
    )
    insert_policy(
        policy_id="policy-disaster-gdacs",
        source_code="disaster_gdacs",
        source_class="event",
        enabled=True,
        fetch_mode="poll_feed",
        schedule_minutes=30,
        freshness_sla_hours=72,
        dedup_key_mode="external_id",
        event_time_field_priority='["event_time","published_at"]',
        severity_mapping_rule="gdacs_alert_level",
        geo_precision_rule="geometry",
        default_params_json='{"alert_levels":["orange","red"]}',
        license_mode="event_feed",
        notes="GDACS alert enrichment layer.",
    )


def downgrade() -> None:
    op.drop_index("ix_source_policies_enabled", table_name="source_policies")
    op.drop_index("ix_source_policies_source_class", table_name="source_policies")
    op.drop_index("ix_source_policies_source_code", table_name="source_policies")
    op.drop_table("source_policies")
