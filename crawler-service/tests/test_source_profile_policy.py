import os
import sqlite3
from pathlib import Path

from news_crawler.utils.source_profile import clear_source_policy_cache, resolve_source_profile


def test_source_profile_uses_database_policy_override(tmp_path):
    db_path = tmp_path / "source-policy.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            create table source_policies (
                id text primary key,
                source_code text not null unique,
                source_class text not null,
                enabled integer not null,
                fetch_mode text not null,
                schedule_minutes integer not null,
                freshness_sla_hours integer not null,
                dedup_key_mode text not null,
                event_time_field_priority text not null,
                severity_mapping_rule text,
                geo_precision_rule text,
                default_params_json text not null,
                license_mode text not null,
                notes text,
                created_at text not null,
                updated_at text not null
            )
            """
        )
        conn.execute(
            """
            insert into source_policies (
                id, source_code, source_class, enabled, fetch_mode, schedule_minutes,
                freshness_sla_hours, dedup_key_mode, event_time_field_priority,
                severity_mapping_rule, geo_precision_rule, default_params_json,
                license_mode, notes, created_at, updated_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """,
            (
                "policy-openai-official",
                "openai_official",
                "lead",
                1,
                "poll_feed",
                360,
                168,
                "canonical_url",
                '["published_at"]',
                None,
                "text_geo",
                '{"status":"open"}',
                "official_public",
                "test override",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    clear_source_policy_cache()

    profile = resolve_source_profile(
        code="openai_official",
        base_url="https://openai.com/news/",
        category="official",
        name="OpenAI News",
    )

    assert profile["source_class"] == "lead"
    assert profile["enabled"] is True
    assert profile["schedule_minutes"] == 360
    assert profile["freshness_sla_hours"] == 168
    assert profile["dedup_key_mode"] == "canonical_url"
    assert profile["event_time_field_priority"] == ["published_at"]
    assert profile["license_mode"] == "official_public"
    assert profile["default_params_json"] == {"status": "open"}
