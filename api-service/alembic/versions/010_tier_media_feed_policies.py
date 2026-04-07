"""add tier media feed policies

Revision ID: 010_tier_media_feeds
Revises: 009_gdacs_enrichment
Create Date: 2026-04-06
"""

from alembic import op
import sqlalchemy as sa


revision = "010_tier_media_feeds"
down_revision = "009_gdacs_enrichment"
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
        policy_id="policy-bbc",
        source_code="bbc",
        source_class="news",
        fetch_mode="poll_feed",
        schedule_minutes=60,
        freshness_sla_hours=24,
        dedup_key_mode="canonical_url",
        event_time_field_priority='["published_at"]',
        geo_precision_rule="text_geo",
        default_params_json='{"feed_urls":["https://www.bbc.com/news/rss.xml"]}',
        license_mode="publisher_public",
        notes="Official BBC RSS feed.",
    )
    upsert_policy(
        policy_id="policy-guardian",
        source_code="guardian",
        source_class="news",
        fetch_mode="poll_feed",
        schedule_minutes=60,
        freshness_sla_hours=24,
        dedup_key_mode="canonical_url",
        event_time_field_priority='["published_at"]',
        geo_precision_rule="text_geo",
        default_params_json='{"feed_urls":["https://www.theguardian.com/tone/news/rss","https://www.theguardian.com/uk-news/rss","https://www.theguardian.com/world/rss"]}',
        license_mode="publisher_public",
        notes="Official Guardian RSS feeds.",
    )
    upsert_policy(
        policy_id="policy-aljazeera",
        source_code="aljazeera",
        source_class="news",
        fetch_mode="poll_feed",
        schedule_minutes=60,
        freshness_sla_hours=24,
        dedup_key_mode="canonical_url",
        event_time_field_priority='["published_at"]',
        geo_precision_rule="text_geo",
        default_params_json='{"feed_urls":["https://www.aljazeera.com/xml/rss/all.xml"]}',
        license_mode="publisher_public",
        notes="Official Al Jazeera RSS feed.",
    )
    upsert_policy(
        policy_id="policy-reuters",
        source_code="reuters",
        source_class="news",
        fetch_mode="poll_feed",
        schedule_minutes=60,
        freshness_sla_hours=24,
        dedup_key_mode="canonical_url",
        event_time_field_priority='["published_at"]',
        geo_precision_rule="text_geo",
        default_params_json='{"fallback":"google_news_site_search","feed_url":"https://news.google.com/rss/search?q=site:reuters.com+when:1d&hl=en-US&gl=US&ceid=US:en"}',
        license_mode="publisher_public",
        notes="Feed-first fallback via Google News site-search RSS because Reuters public feed is bot-protected on current network paths.",
    )
    upsert_policy(
        policy_id="policy-ap",
        source_code="ap",
        source_class="news",
        fetch_mode="poll_feed",
        schedule_minutes=60,
        freshness_sla_hours=24,
        dedup_key_mode="canonical_url",
        event_time_field_priority='["published_at"]',
        geo_precision_rule="text_geo",
        default_params_json='{"fallback":"google_news_site_search","feed_url":"https://news.google.com/rss/search?q=site:apnews.com+when:1d&hl=en-US&gl=US&ceid=US:en"}',
        license_mode="publisher_public",
        notes="Feed-first fallback via Google News site-search RSS because AP public pages are rate-limited on current network paths.",
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM source_policies
            WHERE source_code IN ('bbc', 'guardian', 'aljazeera', 'reuters', 'ap')
            """
        )
    )
