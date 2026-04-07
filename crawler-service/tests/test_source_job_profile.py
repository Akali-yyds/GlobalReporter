import os
import sqlite3

from news_crawler.utils.source_job_profile import (
    clear_source_job_profile_cache,
    resolve_source_job_profile,
    update_source_job_checkpoint,
)


def test_source_job_profile_uses_database_override(tmp_path):
    db_path = tmp_path / "source-job-profile.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            create table source_job_profiles (
                id text primary key,
                job_name text not null unique,
                source_code text not null,
                source_class text not null,
                job_mode text not null,
                window_mode text not null,
                cursor_strategy text not null,
                enabled integer not null,
                schedule_minutes integer not null,
                priority integer not null,
                default_params_json text not null,
                notes text,
                created_at text not null,
                updated_at text not null
            )
            """
        )
        conn.execute(
            """
            create table source_job_checkpoints (
                id text primary key,
                job_name text not null unique,
                source_code text not null,
                job_mode text not null,
                last_success_at text,
                last_seen_external_id text,
                last_seen_source_updated_at text,
                last_event_time text,
                last_seen_page integer,
                last_query_window text,
                created_at text not null,
                updated_at text not null
            )
            """
        )
        conn.execute(
            """
            insert into source_job_profiles (
                id, job_name, source_code, source_class, job_mode, window_mode, cursor_strategy,
                enabled, schedule_minutes, priority, default_params_json, notes, created_at, updated_at
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """,
            (
                "job-eonet-events-rt",
                "eonet_events_realtime",
                "eonet_events",
                "event",
                "realtime",
                "relative",
                "last_seen_source_updated_at",
                1,
                30,
                8,
                '{"status":"open","days":7}',
                "test profile",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    clear_source_job_profile_cache()

    profile = resolve_source_job_profile(
        "eonet_events_realtime",
        {
            "source_code": "eonet_events",
            "source_class": "event",
            "job_mode": "realtime",
            "window_mode": "relative",
            "cursor_strategy": "none",
            "enabled": True,
            "schedule_minutes": 60,
            "priority": 1,
            "default_params_json": {},
            "notes": None,
        },
    )

    assert profile["schedule_minutes"] == 30
    assert profile["default_params_json"] == {"status": "open", "days": 7}

    update_source_job_checkpoint(
        job_name="eonet_events_realtime",
        source_code="eonet_events",
        job_mode="realtime",
        last_success_at="2026-04-06T16:30:00",
        last_seen_external_id="EONET_123",
        last_seen_source_updated_at="2026-04-06T16:20:00",
        last_event_time="2026-04-06T16:10:00",
        last_seen_page=2,
        last_query_window={"fromdate": "2026-04-01", "todate": "2026-04-06"},
    )

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "select last_seen_external_id, last_seen_source_updated_at, last_seen_page, last_query_window from source_job_checkpoints where job_name = ?",
            ("eonet_events_realtime",),
        ).fetchone()
    finally:
        conn.close()

    assert row == (
        "EONET_123",
        "2026-04-06 16:20:00",
        2,
        '{"fromdate": "2026-04-01", "todate": "2026-04-06"}',
    )
