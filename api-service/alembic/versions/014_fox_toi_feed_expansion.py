"""add fox, toi, and feed-aware expansion policies

Revision ID: 014_fox_toi_feed_expansion
Revises: 013_pbs_euronews_nbc_policies
Create Date: 2026-04-06
"""

from alembic import op
import sqlalchemy as sa


revision = "014_fox_toi_feed_expansion"
down_revision = "013_pbs_euronews_nbc_policies"
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
        policy_id="policy-fox-news",
        source_code="fox_news",
        source_class="news",
        fetch_mode="poll_feed",
        schedule_minutes=60,
        freshness_sla_hours=24,
        dedup_key_mode="canonical_url",
        event_time_field_priority='["published_at"]',
        geo_precision_rule="text_geo",
        default_params_json='{"feeds":[{"url":"https://moxie.foxnews.com/google-publisher/latest.xml","name":"latest","priority":1,"freshness_sla_hours":24},{"url":"https://moxie.foxnews.com/google-publisher/world.xml","name":"world","priority":2,"freshness_sla_hours":24},{"url":"https://moxie.foxnews.com/google-publisher/politics.xml","name":"politics","priority":2,"freshness_sla_hours":24}]}',
        license_mode="publisher_public_noncommercial",
        notes="Official Fox News RSS feeds; personal/non-commercial usage restrictions should be respected.",
    )
    upsert_policy(
        policy_id="policy-times-of-india",
        source_code="times_of_india",
        source_class="news",
        fetch_mode="poll_feed",
        schedule_minutes=90,
        freshness_sla_hours=24,
        dedup_key_mode="canonical_url",
        event_time_field_priority='["published_at"]',
        geo_precision_rule="text_geo",
        default_params_json='{"feeds":[{"url":"https://timesofindia.indiatimes.com/rssfeedstopstories.cms","name":"top_stories","priority":1,"freshness_sla_hours":24},{"url":"https://timesofindia.indiatimes.com/rssfeeds/296589292.cms","name":"world","priority":2,"freshness_sla_hours":24},{"url":"https://timesofindia.indiatimes.com/rssfeeds/1898055.cms","name":"business","priority":2,"freshness_sla_hours":24}]}',
        license_mode="publisher_public_noncommercial",
        notes="Official Times of India RSS feeds; personal/non-commercial usage restrictions should be respected.",
    )
    upsert_policy(
        policy_id="policy-pbs-feed-expansion",
        source_code="pbs_newshour",
        source_class="news",
        fetch_mode="poll_feed",
        schedule_minutes=90,
        freshness_sla_hours=24,
        dedup_key_mode="canonical_url",
        event_time_field_priority='["published_at"]',
        geo_precision_rule="text_geo",
        default_params_json='{"feeds":[{"url":"https://www.pbs.org/newshour/feeds/rss/headlines","name":"headlines","priority":1,"freshness_sla_hours":24},{"url":"https://www.pbs.org/newshour/feeds/rss/politics","name":"politics","priority":2,"freshness_sla_hours":24}]}',
        license_mode="publisher_public",
        notes="Official PBS NewsHour RSS feeds with headlines prioritized over politics.",
    )
    upsert_policy(
        policy_id="policy-euronews-feed-expansion",
        source_code="euronews",
        source_class="news",
        fetch_mode="poll_feed",
        schedule_minutes=60,
        freshness_sla_hours=24,
        dedup_key_mode="canonical_url",
        event_time_field_priority='["published_at"]',
        geo_precision_rule="text_geo",
        default_params_json='{"feeds":[{"url":"https://www.euronews.com/rss?format=mrss&level=theme&name=news","name":"world_news","priority":2,"freshness_sla_hours":24},{"url":"https://www.euronews.com/rss?format=mrss&level=vertical&name=my-europe","name":"my_europe","priority":2,"freshness_sla_hours":24}]}',
        license_mode="publisher_public",
        notes="Official Euronews public RSS feeds for world news and My Europe.",
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM source_policies
            WHERE source_code IN ('fox_news', 'times_of_india')
            """
        )
    )
