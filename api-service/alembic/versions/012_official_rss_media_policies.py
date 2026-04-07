"""add official rss media policies

Revision ID: 012_official_rss_media_policies
Revises: 011_asia_feed_policies
Create Date: 2026-04-06
"""

from alembic import op
import sqlalchemy as sa


revision = "012_official_rss_media_policies"
down_revision = "011_asia_feed_policies"
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
        policy_id="policy-ndtv",
        source_code="ndtv",
        source_class="news",
        fetch_mode="poll_feed",
        schedule_minutes=90,
        freshness_sla_hours=24,
        dedup_key_mode="canonical_url",
        event_time_field_priority='["published_at"]',
        geo_precision_rule="text_geo",
        default_params_json='{"feed_urls":["https://feeds.feedburner.com/ndtvnews-top-stories","https://feeds.feedburner.com/ndtvnews-world-news"]}',
        license_mode="publisher_public_noncommercial",
        notes="Official NDTV RSS; personal/non-commercial usage restrictions should be respected.",
    )
    upsert_policy(
        policy_id="policy-abc-news",
        source_code="abc_news",
        source_class="news",
        fetch_mode="poll_feed",
        schedule_minutes=60,
        freshness_sla_hours=24,
        dedup_key_mode="canonical_url",
        event_time_field_priority='["published_at"]',
        geo_precision_rule="text_geo",
        default_params_json='{"feed_urls":["https://feeds.abcnews.com/abcnews/topstories","https://feeds.abcnews.com/abcnews/internationalheadlines"]}',
        license_mode="publisher_public",
        notes="Official ABC News RSS feeds for top stories and international headlines.",
    )
    upsert_policy(
        policy_id="policy-voa",
        source_code="voa",
        source_class="news",
        fetch_mode="poll_feed",
        schedule_minutes=180,
        freshness_sla_hours=24,
        dedup_key_mode="canonical_url",
        event_time_field_priority='["published_at"]',
        geo_precision_rule="text_geo",
        default_params_json='{"feed_urls":["https://www.voanews.com/api/"],"rollout":"poc_only"}',
        license_mode="publisher_public",
        notes="Official VOA RSS validated, but kept as PoC only because current feed freshness does not consistently satisfy the 24h SLA.",
    )
    upsert_policy(
        policy_id="policy-cbs-news",
        source_code="cbs_news",
        source_class="news",
        fetch_mode="poll_feed",
        schedule_minutes=90,
        freshness_sla_hours=24,
        dedup_key_mode="canonical_url",
        event_time_field_priority='["published_at"]',
        geo_precision_rule="text_geo",
        default_params_json='{"feed_urls":["https://www.cbsnews.com/latest/rss/main"]}',
        license_mode="publisher_public",
        notes="Official CBS News RSS main feed.",
    )
    upsert_policy(
        policy_id="policy-sky-news",
        source_code="sky_news",
        source_class="news",
        fetch_mode="poll_feed",
        schedule_minutes=60,
        freshness_sla_hours=24,
        dedup_key_mode="canonical_url",
        event_time_field_priority='["published_at"]',
        geo_precision_rule="text_geo",
        default_params_json='{"feed_urls":["http://feeds.skynews.com/feeds/rss/world.xml","http://feeds.skynews.com/feeds/rss/home.xml"]}',
        license_mode="publisher_public",
        notes="Official Sky News RSS feeds for world and home coverage.",
    )
    upsert_policy(
        policy_id="policy-nhk-world",
        source_code="nhk_world",
        source_class="news",
        fetch_mode="poll_feed",
        schedule_minutes=180,
        freshness_sla_hours=24,
        dedup_key_mode="canonical_url",
        event_time_field_priority='["published_at"]',
        geo_precision_rule="text_geo",
        default_params_json='{"feed_urls":["https://www3.nhk.or.jp/rss/news/cat0.xml","https://www3.nhk.or.jp/rss/news/cat6.xml"],"rollout":"poc_only"}',
        license_mode="publisher_public",
        notes="NHK World RSS PoC only; keep out of default rollout until feed stability is re-validated.",
    )
    upsert_policy(
        policy_id="policy-france24-poc",
        source_code="france24",
        source_class="news",
        fetch_mode="poll_feed",
        schedule_minutes=180,
        freshness_sla_hours=24,
        dedup_key_mode="canonical_url",
        event_time_field_priority='["published_at"]',
        geo_precision_rule="text_geo",
        default_params_json='{"feed_urls":["https://www.france24.com/en/rss"],"rollout":"poc_only"}',
        license_mode="publisher_public",
        notes="France24 RSS remains PoC only; not part of default rollout until feed stability is re-validated.",
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM source_policies
            WHERE source_code IN ('abc_news', 'voa', 'cbs_news', 'sky_news', 'nhk_world')
            """
        )
    )
