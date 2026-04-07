"""add pbs euronews nbc source policies

Revision ID: 013_pbs_euronews_nbc_policies
Revises: 012_official_rss_media_policies
Create Date: 2026-04-06
"""

from alembic import op
import sqlalchemy as sa


revision = "013_pbs_euronews_nbc_policies"
down_revision = "012_official_rss_media_policies"
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
        policy_id="policy-abc-news-feed-aware",
        source_code="abc_news",
        source_class="news",
        fetch_mode="poll_feed",
        schedule_minutes=60,
        freshness_sla_hours=24,
        dedup_key_mode="canonical_url",
        event_time_field_priority='["published_at"]',
        geo_precision_rule="text_geo",
        default_params_json='{"feeds":[{"url":"https://feeds.abcnews.com/abcnews/internationalheadlines","name":"international_headlines","priority":1,"freshness_sla_hours":24},{"url":"https://feeds.abcnews.com/abcnews/topstories","name":"top_stories","priority":2,"freshness_sla_hours":24}],"candidate_multiplier":5}',
        license_mode="publisher_public",
        notes="Official ABC News RSS feeds with feed-level priority and freshness metadata.",
    )
    upsert_policy(
        policy_id="policy-voa-feed-aware",
        source_code="voa",
        source_class="news",
        fetch_mode="poll_feed",
        schedule_minutes=180,
        freshness_sla_hours=24,
        dedup_key_mode="canonical_url",
        event_time_field_priority='["published_at"]',
        geo_precision_rule="text_geo",
        default_params_json='{"feeds":[{"url":"https://www.voanews.com/api/","name":"top_stories","priority":1,"freshness_sla_hours":24}],"rollout":"poc_only"}',
        license_mode="publisher_public",
        notes="Official VOA RSS validated, but kept as PoC only because current feed freshness does not consistently satisfy the 24h SLA.",
    )
    upsert_policy(
        policy_id="policy-pbs-newshour",
        source_code="pbs_newshour",
        source_class="news",
        fetch_mode="poll_feed",
        schedule_minutes=90,
        freshness_sla_hours=24,
        dedup_key_mode="canonical_url",
        event_time_field_priority='["published_at"]',
        geo_precision_rule="text_geo",
        default_params_json='{"feeds":[{"url":"https://www.pbs.org/newshour/feeds/rss/headlines","name":"headlines","priority":1,"freshness_sla_hours":24}]}',
        license_mode="publisher_public",
        notes="Official PBS NewsHour RSS headlines feed.",
    )
    upsert_policy(
        policy_id="policy-euronews",
        source_code="euronews",
        source_class="news",
        fetch_mode="poll_feed",
        schedule_minutes=60,
        freshness_sla_hours=24,
        dedup_key_mode="canonical_url",
        event_time_field_priority='["published_at"]',
        geo_precision_rule="text_geo",
        default_params_json='{"feeds":[{"url":"https://www.euronews.com/rss?format=mrss&level=theme&name=news","name":"world_news","priority":1,"freshness_sla_hours":24}]}',
        license_mode="publisher_public",
        notes="Official Euronews public RSS feed for world news.",
    )
    upsert_policy(
        policy_id="policy-nbc-news",
        source_code="nbc_news",
        source_class="news",
        fetch_mode="poll_feed",
        schedule_minutes=180,
        freshness_sla_hours=24,
        dedup_key_mode="canonical_url",
        event_time_field_priority='["published_at"]',
        geo_precision_rule="text_geo",
        default_params_json='{"feeds":[{"url":"https://feeds.nbcnews.com/nbcnews/public/news","name":"public_news","priority":1,"freshness_sla_hours":24}],"rollout":"poc_only"}',
        license_mode="publisher_public",
        notes="NBC News RSS PoC only; not in default rollout until a stronger official RSS evidence chain is adopted.",
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM source_policies
            WHERE source_code IN ('pbs_newshour', 'euronews', 'nbc_news')
            """
        )
    )
