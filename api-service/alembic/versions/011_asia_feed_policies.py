"""add asia and ft feed policies

Revision ID: 011_asia_feed_policies
Revises: 010_tier_media_feeds
Create Date: 2026-04-06
"""

from alembic import op
import sqlalchemy as sa


revision = "011_asia_feed_policies"
down_revision = "010_tier_media_feeds"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    json_type = "jsonb" if conn.dialect.name == "postgresql" else "json"

    def upsert_policy(
        *,
        policy_id: str,
        source_code: str,
        source_class: str,
        fetch_mode: str,
        schedule_minutes: int,
        freshness_sla_hours: int,
        dedup_key_mode: str,
        event_time_field_priority: str,
        geo_precision_rule: str,
        default_params_json: str,
        license_mode: str,
        notes: str,
    ) -> None:
        exists = conn.execute(
            sa.text("SELECT 1 FROM source_policies WHERE source_code = :source_code"),
            {"source_code": source_code},
        ).first()

        if exists:
            op.execute(
                sa.text(
                    f"""
                    UPDATE source_policies
                    SET source_class = :source_class,
                        enabled = TRUE,
                        fetch_mode = :fetch_mode,
                        schedule_minutes = :schedule_minutes,
                        freshness_sla_hours = :freshness_sla_hours,
                        dedup_key_mode = :dedup_key_mode,
                        event_time_field_priority = CAST(:event_time_field_priority AS {json_type}),
                        severity_mapping_rule = NULL,
                        geo_precision_rule = :geo_precision_rule,
                        default_params_json = CAST(:default_params_json AS {json_type}),
                        license_mode = :license_mode,
                        notes = :notes,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE source_code = :source_code
                    """
                ).bindparams(
                    source_code=source_code,
                    source_class=source_class,
                    fetch_mode=fetch_mode,
                    schedule_minutes=schedule_minutes,
                    freshness_sla_hours=freshness_sla_hours,
                    dedup_key_mode=dedup_key_mode,
                    event_time_field_priority=event_time_field_priority,
                    geo_precision_rule=geo_precision_rule,
                    default_params_json=default_params_json,
                    license_mode=license_mode,
                    notes=notes,
                )
            )
            return

        op.execute(
            sa.text(
                f"""
                INSERT INTO source_policies (
                    id, source_code, source_class, enabled, fetch_mode, schedule_minutes,
                    freshness_sla_hours, dedup_key_mode, event_time_field_priority,
                    severity_mapping_rule, geo_precision_rule, default_params_json,
                    license_mode, notes, created_at, updated_at
                ) VALUES (
                    :id, :source_code, :source_class, TRUE, :fetch_mode, :schedule_minutes,
                    :freshness_sla_hours, :dedup_key_mode,
                    CAST(:event_time_field_priority AS {json_type}),
                    NULL, :geo_precision_rule, CAST(:default_params_json AS {json_type}),
                    :license_mode, :notes, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """
            ).bindparams(
                id=policy_id,
                source_code=source_code,
                source_class=source_class,
                fetch_mode=fetch_mode,
                schedule_minutes=schedule_minutes,
                freshness_sla_hours=freshness_sla_hours,
                dedup_key_mode=dedup_key_mode,
                event_time_field_priority=event_time_field_priority,
                geo_precision_rule=geo_precision_rule,
                default_params_json=default_params_json,
                license_mode=license_mode,
                notes=notes,
            )
        )

    upsert_policy(
        policy_id="policy-cna",
        source_code="cna",
        source_class="news",
        fetch_mode="poll_feed",
        schedule_minutes=60,
        freshness_sla_hours=24,
        dedup_key_mode="canonical_url",
        event_time_field_priority='["published_at"]',
        geo_precision_rule="text_geo",
        default_params_json='{"feed_urls":["https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml&category=6311","https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml"]}',
        license_mode="publisher_public_noncommercial",
        notes="Official CNA RSS; personal/non-commercial usage restrictions should be respected.",
    )
    upsert_policy(
        policy_id="policy-dw",
        source_code="dw",
        source_class="news",
        fetch_mode="poll_feed",
        schedule_minutes=90,
        freshness_sla_hours=24,
        dedup_key_mode="canonical_url",
        event_time_field_priority='["published_at"]',
        geo_precision_rule="text_geo",
        default_params_json='{"feed_urls":["https://rss.dw.com/rdf/rss-en-world","https://rss.dw.com/rdf/rss-en-all"]}',
        license_mode="publisher_public",
        notes="Official DW English RSS feeds.",
    )
    upsert_policy(
        policy_id="policy-scmp",
        source_code="scmp",
        source_class="news",
        fetch_mode="poll_feed",
        schedule_minutes=60,
        freshness_sla_hours=24,
        dedup_key_mode="canonical_url",
        event_time_field_priority='["published_at"]',
        geo_precision_rule="text_geo",
        default_params_json='{"feed_urls":["https://www.scmp.com/rss/91/feed","https://www.scmp.com/rss/4/feed"]}',
        license_mode="publisher_public",
        notes="Official SCMP RSS feeds for world and China coverage.",
    )
    upsert_policy(
        policy_id="policy-straits-times",
        source_code="straits_times",
        source_class="news",
        fetch_mode="poll_feed",
        schedule_minutes=90,
        freshness_sla_hours=24,
        dedup_key_mode="canonical_url",
        event_time_field_priority='["published_at"]',
        geo_precision_rule="text_geo",
        default_params_json='{"feed_urls":["https://www.straitstimes.com/news/world/rss.xml","https://www.straitstimes.com/news/asia/rss.xml"]}',
        license_mode="publisher_public",
        notes="Official Straits Times section RSS feeds for world and Asia coverage.",
    )
    upsert_policy(
        policy_id="policy-ft",
        source_code="ft",
        source_class="news",
        fetch_mode="poll_feed",
        schedule_minutes=180,
        freshness_sla_hours=24,
        dedup_key_mode="canonical_url",
        event_time_field_priority='["published_at"]',
        geo_precision_rule="text_geo",
        default_params_json='{"feed_urls":["https://www.ft.com/rss/home/international"],"rollout":"poc_only"}',
        license_mode="publisher_public",
        notes="FT official RSS PoC only; not part of default scheduler rotation yet.",
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM source_policies
            WHERE source_code IN ('cna', 'dw', 'scmp', 'straits_times', 'ft')
            """
        )
    )
