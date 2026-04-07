"""add feed control plane tables

Revision ID: 015_feed_control_plane
Revises: 014_fox_toi_feed_expansion
Create Date: 2026-04-06
"""

from __future__ import annotations

import json
import math
import re
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision = "015_feed_control_plane"
down_revision = "014_fox_toi_feed_expansion"
branch_labels = None
depends_on = None


def _normalize_json(value):
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {}
    return {}


def _slug(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", (value or "").strip().lower()).strip("_")
    return cleaned or fallback


def _rollout_from_row(feed: dict, notes: str | None) -> str:
    explicit = str(feed.get("rollout_state") or feed.get("rollout") or "").strip().lower()
    if explicit in {"draft", "poc", "canary", "default", "paused"}:
        return explicit
    note_text = (notes or "").strip().lower()
    if "poc" in note_text:
        return "poc"
    if "canary" in note_text:
        return "canary"
    return "default"


def upgrade() -> None:
    op.create_table(
        "source_feed_profiles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("source_code", sa.String(length=50), nullable=False),
        sa.Column("feed_code", sa.String(length=80), nullable=False),
        sa.Column("feed_url", sa.String(length=2000), nullable=False),
        sa.Column("feed_name", sa.String(length=120), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("freshness_sla_hours", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("rollout_state", sa.String(length=20), nullable=False, server_default="default"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("expected_update_interval_hours", sa.Integer(), nullable=False, server_default="24"),
        sa.Column("license_mode", sa.String(length=40), nullable=False, server_default="public_web"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_code", "feed_code", name="uq_source_feed_profiles_source_feed"),
    )
    op.create_index("ix_source_feed_profiles_source_code", "source_feed_profiles", ["source_code"])
    op.create_index("ix_source_feed_profiles_feed_code", "source_feed_profiles", ["feed_code"])
    op.create_index("ix_source_feed_profiles_priority", "source_feed_profiles", ["priority"])
    op.create_index("ix_source_feed_profiles_rollout_state", "source_feed_profiles", ["rollout_state"])
    op.create_index("ix_source_feed_profiles_enabled", "source_feed_profiles", ["enabled"])

    op.create_table(
        "source_feed_health",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("source_code", sa.String(length=50), nullable=False),
        sa.Column("feed_code", sa.String(length=80), nullable=False),
        sa.Column("feed_profile_id", sa.String(length=36), nullable=True),
        sa.Column("last_fetch_at", sa.DateTime(), nullable=True),
        sa.Column("last_success_at", sa.DateTime(), nullable=True),
        sa.Column("last_fresh_item_at", sa.DateTime(), nullable=True),
        sa.Column("last_http_status", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("scraped_count_24h", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("dropped_stale_count_24h", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("dropped_quality_count_24h", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stale_ratio_24h", sa.Float(), nullable=False, server_default="0"),
        sa.Column("direct_ok_rate_24h", sa.Float(), nullable=False, server_default="0"),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("direct_attempt_count_24h", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("direct_ok_count_24h", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("window_started_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_code", "feed_code", name="uq_source_feed_health_source_feed"),
    )
    op.create_index("ix_source_feed_health_source_code", "source_feed_health", ["source_code"])
    op.create_index("ix_source_feed_health_feed_code", "source_feed_health", ["feed_code"])
    op.create_index("ix_source_feed_health_feed_profile_id", "source_feed_health", ["feed_profile_id"])
    op.create_index("ix_source_feed_health_last_fetch_at", "source_feed_health", ["last_fetch_at"])
    op.create_index("ix_source_feed_health_last_success_at", "source_feed_health", ["last_success_at"])
    op.create_index("ix_source_feed_health_last_fresh_item_at", "source_feed_health", ["last_fresh_item_at"])
    op.create_index("ix_source_feed_health_window_started_at", "source_feed_health", ["window_started_at"])

    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            """
            SELECT source_code, schedule_minutes, freshness_sla_hours, default_params_json, license_mode, notes
            FROM source_policies
            """
        )
    ).mappings().all()

    for row in rows:
        params = _normalize_json(row["default_params_json"])
        feed_rows = params.get("feeds") or []
        feed_urls = params.get("feed_urls") or []
        if not isinstance(feed_rows, list):
            feed_rows = []
        if not feed_rows and isinstance(feed_urls, list):
            for index, url in enumerate(feed_urls):
                feed_rows.append(
                    {
                        "url": url,
                        "name": f"feed_{index + 1}",
                        "priority": index + 1,
                    }
                )
        if not feed_rows:
            continue

        base_expected_hours = max(1, int(math.ceil((row["schedule_minutes"] or 60) / 60)))
        for index, feed in enumerate(feed_rows):
            feed_url = str(feed.get("url") or "").strip()
            if not feed_url:
                continue
            feed_name = str(feed.get("name") or feed.get("feed_name") or f"feed_{index + 1}").strip()
            feed_code = _slug(str(feed.get("feed_code") or feed_name), f"feed_{index + 1}")
            conn.execute(
                sa.text(
                    """
                    INSERT INTO source_feed_profiles (
                        id, created_at, updated_at, source_code, feed_code, feed_url, feed_name,
                        priority, freshness_sla_hours, rollout_state, enabled,
                        expected_update_interval_hours, license_mode, notes
                    ) VALUES (
                        :id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, :source_code, :feed_code, :feed_url, :feed_name,
                        :priority, :freshness_sla_hours, :rollout_state, :enabled,
                        :expected_update_interval_hours, :license_mode, :notes
                    )
                    ON CONFLICT (source_code, feed_code) DO NOTHING
                    """
                ),
                {
                    "id": str(uuid4()),
                    "source_code": row["source_code"],
                    "feed_code": feed_code,
                    "feed_url": feed_url,
                    "feed_name": feed_name,
                    "priority": int(feed.get("priority") or (index + 1)),
                    "freshness_sla_hours": int(feed.get("freshness_sla_hours") or row["freshness_sla_hours"] or 24),
                    "rollout_state": _rollout_from_row(feed, row["notes"]),
                    "enabled": bool(feed.get("enabled", True)),
                    "expected_update_interval_hours": int(feed.get("expected_update_interval_hours") or base_expected_hours),
                    "license_mode": str(feed.get("license_mode") or row["license_mode"] or "public_web"),
                    "notes": feed.get("notes") or row["notes"],
                },
            )


def downgrade() -> None:
    op.drop_index("ix_source_feed_health_window_started_at", table_name="source_feed_health")
    op.drop_index("ix_source_feed_health_last_fresh_item_at", table_name="source_feed_health")
    op.drop_index("ix_source_feed_health_last_success_at", table_name="source_feed_health")
    op.drop_index("ix_source_feed_health_last_fetch_at", table_name="source_feed_health")
    op.drop_index("ix_source_feed_health_feed_profile_id", table_name="source_feed_health")
    op.drop_index("ix_source_feed_health_feed_code", table_name="source_feed_health")
    op.drop_index("ix_source_feed_health_source_code", table_name="source_feed_health")
    op.drop_table("source_feed_health")

    op.drop_index("ix_source_feed_profiles_enabled", table_name="source_feed_profiles")
    op.drop_index("ix_source_feed_profiles_rollout_state", table_name="source_feed_profiles")
    op.drop_index("ix_source_feed_profiles_priority", table_name="source_feed_profiles")
    op.drop_index("ix_source_feed_profiles_feed_code", table_name="source_feed_profiles")
    op.drop_index("ix_source_feed_profiles_source_code", table_name="source_feed_profiles")
    op.drop_table("source_feed_profiles")
