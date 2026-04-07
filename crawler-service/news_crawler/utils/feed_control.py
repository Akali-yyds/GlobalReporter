"""Feed-level control plane helpers for crawler spiders."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import create_engine, text


_FEED_CACHE_TTL_SECONDS = 120
_FEED_CACHE: dict[tuple[str, str], tuple[float, list[dict[str, Any]]]] = {}
_ENGINE = None

_ROLLOUT_SCOPE_ALLOWLIST = {
    "default": {"default"},
    "canary": {"canary"},
    "poc": {"poc"},
    "all": {"default", "canary", "poc", "draft"},
    "draft": {"draft"},
    "paused": {"paused"},
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _ensure_env_loaded() -> None:
    if os.getenv("DATABASE_URL"):
        return
    try:
        from dotenv import load_dotenv

        repo_root = Path(__file__).resolve().parents[3]
        env_file = repo_root / ".env"
        if env_file.is_file():
            load_dotenv(env_file)
    except Exception:
        return


def _get_engine():
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE
    _ensure_env_loaded()
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        return None
    _ENGINE = create_engine(db_url, pool_pre_ping=True)
    return _ENGINE


def clear_feed_cache() -> None:
    global _ENGINE
    _FEED_CACHE.clear()
    if _ENGINE is not None:
        _ENGINE.dispose()
        _ENGINE = None


def _normalize_rollout_state(value: Any, *, default: str = "default") -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"draft", "poc", "canary", "default", "paused"}:
        return normalized
    if normalized == "poc_only":
        return "poc"
    return default


def _normalize_feed_code(value: str, fallback: str) -> str:
    chars = []
    for ch in (value or fallback or "").strip().lower():
        if ch.isalnum():
            chars.append(ch)
        else:
            chars.append("_")
    result = "".join(chars).strip("_")
    while "__" in result:
        result = result.replace("__", "_")
    return result or fallback


def _cached_feed_rows(source_code: str, feed_scope: str) -> list[dict[str, Any]] | None:
    now = time.time()
    cache_key = (source_code, feed_scope)
    cached = _FEED_CACHE.get(cache_key)
    if cached and now - cached[0] < _FEED_CACHE_TTL_SECONDS:
        return cached[1]

    engine = _get_engine()
    if engine is None:
        return None

    allowed = _ROLLOUT_SCOPE_ALLOWLIST.get(feed_scope, _ROLLOUT_SCOPE_ALLOWLIST["default"])
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id, source_code, feed_code, feed_url, feed_name, priority,
                           freshness_sla_hours, rollout_state, enabled,
                           expected_update_interval_hours, license_mode, notes
                    FROM source_feed_profiles
                    WHERE source_code = :source_code
                      AND enabled = TRUE
                    ORDER BY priority ASC, feed_name ASC
                    """
                ),
                {"source_code": source_code},
            ).mappings().all()
    except Exception:
        rows = []

    profiles = [
        {
            "id": row["id"],
            "source_code": row["source_code"],
            "code": row["feed_code"],
            "url": row["feed_url"],
            "name": row["feed_name"],
            "priority": int(row["priority"] or 100),
            "freshness_sla_hours": int(row["freshness_sla_hours"] or 24),
            "rollout_state": _normalize_rollout_state(row["rollout_state"]),
            "enabled": bool(row["enabled"]),
            "expected_update_interval_hours": int(row["expected_update_interval_hours"] or 24),
            "license_mode": row["license_mode"] or "public_web",
            "notes": row["notes"],
        }
        for row in rows
        if _normalize_rollout_state(row["rollout_state"]) in allowed
    ]
    _FEED_CACHE[cache_key] = (now, profiles)
    return profiles


def resolve_feed_profiles(
    source_code: str,
    fallback_feeds: list[dict[str, Any]],
    *,
    feed_scope: str = "default",
) -> list[dict[str, Any]]:
    rows = _cached_feed_rows(source_code, feed_scope)
    if rows:
        return rows

    allowed = _ROLLOUT_SCOPE_ALLOWLIST.get(feed_scope, _ROLLOUT_SCOPE_ALLOWLIST["default"])
    profiles: list[dict[str, Any]] = []
    for index, feed in enumerate(fallback_feeds or []):
        rollout_state = _normalize_rollout_state(feed.get("rollout_state") or feed.get("rollout"), default="default")
        if rollout_state not in allowed:
            continue
        profiles.append(
            {
                "id": None,
                "source_code": source_code,
                "code": _normalize_feed_code(str(feed.get("code") or feed.get("name") or f"feed_{index + 1}"), f"feed_{index + 1}"),
                "url": str(feed.get("url") or "").strip(),
                "name": str(feed.get("name") or f"feed_{index + 1}").strip(),
                "priority": int(feed.get("priority") or (index + 1)),
                "freshness_sla_hours": int(feed.get("freshness_sla_hours") or 24),
                "rollout_state": rollout_state,
                "enabled": bool(feed.get("enabled", True)),
                "expected_update_interval_hours": int(feed.get("expected_update_interval_hours") or 24),
                "license_mode": str(feed.get("license_mode") or "public_web"),
                "notes": feed.get("notes"),
            }
        )
    return profiles


def initialize_feed_runtime(spider, feeds: list[dict[str, Any]]) -> None:
    runtime = {}
    for feed in feeds:
        runtime[feed["code"]] = {
            "feed_code": feed["code"],
            "feed_name": feed["name"],
            "feed_url": feed["url"],
            "last_fetch_at": None,
            "last_success_at": None,
            "last_fresh_item_at": None,
            "last_http_status": None,
            "last_error": None,
            "scraped_count_24h": 0,
            "dropped_stale_count_24h": 0,
            "dropped_quality_count_24h": 0,
            "direct_attempt_count_24h": 0,
            "direct_ok_count_24h": 0,
            "consecutive_failures": 0,
        }
    spider._feed_runtime = runtime
    spider._feed_configs_by_url = {feed["url"]: feed for feed in feeds}
    spider._feed_configs_by_code = {feed["code"]: feed for feed in feeds}


def feed_for_response(spider, response, fallback_feeds: list[dict[str, Any]]) -> dict[str, Any]:
    url = getattr(response, "url", "") or ""
    profile = getattr(spider, "_feed_configs_by_url", {}).get(url)
    if profile:
        return profile
    for index, feed in enumerate(fallback_feeds or []):
        if str(feed.get("url") or "").strip() == url:
            return {
                "id": None,
                "source_code": spider.source_code,
                "code": _normalize_feed_code(str(feed.get("code") or feed.get("name") or f"feed_{index + 1}"), f"feed_{index + 1}"),
                "url": url,
                "name": str(feed.get("name") or f"feed_{index + 1}").strip(),
                "priority": int(feed.get("priority") or (index + 1)),
                "freshness_sla_hours": int(feed.get("freshness_sla_hours") or 24),
                "rollout_state": _normalize_rollout_state(feed.get("rollout_state") or feed.get("rollout"), default="default"),
                "enabled": bool(feed.get("enabled", True)),
                "expected_update_interval_hours": int(feed.get("expected_update_interval_hours") or 24),
                "license_mode": str(feed.get("license_mode") or "public_web"),
                "notes": feed.get("notes"),
            }
    resolved = resolve_feed_profiles(spider.source_code, fallback_feeds, feed_scope=getattr(spider, "feed_scope", "default"))
    return resolved[0] if resolved else {
        "id": None,
        "source_code": spider.source_code,
        "code": "default",
        "url": url,
        "name": "default",
        "priority": 100,
        "freshness_sla_hours": 24,
        "rollout_state": "default",
        "enabled": True,
        "expected_update_interval_hours": 24,
        "license_mode": "public_web",
        "notes": None,
    }


def build_feed_request_meta(feed: dict[str, Any]) -> dict[str, Any]:
    return {
        "feed_code": feed["code"],
        "feed_name": feed["name"],
        "feed_priority": feed["priority"],
        "feed_freshness_sla_hours": feed["freshness_sla_hours"],
        "feed_rollout_state": feed["rollout_state"],
        "feed_profile_id": feed.get("id"),
    }


def record_feed_fetch(
    spider,
    *,
    feed_code: str,
    feed_name: str | None = None,
    feed_url: str | None = None,
    http_status: int | None = None,
    success: bool,
    error: str | None = None,
) -> None:
    runtime = getattr(spider, "_feed_runtime", None) or {}
    bucket = runtime.setdefault(
        feed_code,
        {
            "feed_code": feed_code,
            "feed_name": feed_name or feed_code,
            "feed_url": feed_url,
            "last_fetch_at": None,
            "last_success_at": None,
            "last_fresh_item_at": None,
            "last_http_status": None,
            "last_error": None,
            "scraped_count_24h": 0,
            "dropped_stale_count_24h": 0,
            "dropped_quality_count_24h": 0,
            "direct_attempt_count_24h": 0,
            "direct_ok_count_24h": 0,
            "consecutive_failures": 0,
        },
    )
    now = _utcnow()
    bucket["feed_name"] = feed_name or bucket["feed_name"]
    bucket["feed_url"] = feed_url or bucket["feed_url"]
    bucket["last_fetch_at"] = now
    bucket["last_http_status"] = http_status
    bucket["last_error"] = error
    if success:
        bucket["last_success_at"] = now
        bucket["consecutive_failures"] = 0
    else:
        bucket["consecutive_failures"] = int(bucket.get("consecutive_failures") or 0) + 1


def _feed_bucket_for_item(spider, adapter) -> dict[str, Any] | None:
    metadata = adapter.get("source_metadata") or {}
    feed_code = str(metadata.get("feed_code") or "").strip()
    if not feed_code:
        feed_name = str(metadata.get("feed_name") or "").strip()
        feed_code = _normalize_feed_code(feed_name, "default")
    runtime = getattr(spider, "_feed_runtime", None) or {}
    return runtime.get(feed_code)


def record_feed_scraped(spider, adapter) -> None:
    bucket = _feed_bucket_for_item(spider, adapter)
    if not bucket:
        return
    bucket["scraped_count_24h"] = int(bucket.get("scraped_count_24h") or 0) + 1


def record_feed_quality_drop(spider, adapter) -> None:
    bucket = _feed_bucket_for_item(spider, adapter)
    if not bucket:
        return
    bucket["dropped_quality_count_24h"] = int(bucket.get("dropped_quality_count_24h") or 0) + 1


def record_feed_stale_drop(spider, adapter) -> None:
    bucket = _feed_bucket_for_item(spider, adapter)
    if not bucket:
        return
    bucket["dropped_stale_count_24h"] = int(bucket.get("dropped_stale_count_24h") or 0) + 1


def record_feed_fresh_item(spider, adapter) -> None:
    bucket = _feed_bucket_for_item(spider, adapter)
    if not bucket:
        return
    bucket["last_fresh_item_at"] = _utcnow()


def record_feed_direct_result(spider, adapter, *, direct_ok: bool) -> None:
    bucket = _feed_bucket_for_item(spider, adapter)
    if not bucket:
        return
    bucket["direct_attempt_count_24h"] = int(bucket.get("direct_attempt_count_24h") or 0) + 1
    if direct_ok:
        bucket["direct_ok_count_24h"] = int(bucket.get("direct_ok_count_24h") or 0) + 1


def flush_feed_health(spider) -> None:
    runtime = getattr(spider, "_feed_runtime", None) or {}
    if not runtime:
        return

    engine = _get_engine()
    if engine is None:
        return

    now = _utcnow()
    with engine.begin() as conn:
        existing_rows = conn.execute(
            text(
                """
                SELECT source_code, feed_code, feed_profile_id, window_started_at,
                       scraped_count_24h, dropped_stale_count_24h, dropped_quality_count_24h,
                       direct_attempt_count_24h, direct_ok_count_24h, consecutive_failures
                FROM source_feed_health
                WHERE source_code = :source_code
                """
            ),
            {"source_code": spider.source_code},
        ).mappings().all()
        existing = {row["feed_code"]: row for row in existing_rows}

        profiles = conn.execute(
            text(
                """
                SELECT id, feed_code, rollout_state, enabled, notes
                FROM source_feed_profiles
                WHERE source_code = :source_code
                """
            ),
            {"source_code": spider.source_code},
        ).mappings().all()
        profile_map = {row["feed_code"]: row for row in profiles}

        for feed_code, bucket in runtime.items():
            row = existing.get(feed_code)
            profile = profile_map.get(feed_code)
            window_started_at = row["window_started_at"] if row else None
            if window_started_at is None or (now - window_started_at).total_seconds() >= 24 * 3600:
                base_scraped = 0
                base_stale = 0
                base_quality = 0
                base_direct_attempt = 0
                base_direct_ok = 0
                window_started_at = now
            else:
                base_scraped = int(row["scraped_count_24h"] or 0)
                base_stale = int(row["dropped_stale_count_24h"] or 0)
                base_quality = int(row["dropped_quality_count_24h"] or 0)
                base_direct_attempt = int(row["direct_attempt_count_24h"] or 0)
                base_direct_ok = int(row["direct_ok_count_24h"] or 0)

            scraped_count = base_scraped + int(bucket.get("scraped_count_24h") or 0)
            dropped_stale_count = base_stale + int(bucket.get("dropped_stale_count_24h") or 0)
            dropped_quality_count = base_quality + int(bucket.get("dropped_quality_count_24h") or 0)
            direct_attempt_count = base_direct_attempt + int(bucket.get("direct_attempt_count_24h") or 0)
            direct_ok_count = base_direct_ok + int(bucket.get("direct_ok_count_24h") or 0)
            stale_ratio = round(dropped_stale_count / scraped_count, 4) if scraped_count > 0 else 0.0
            direct_ok_rate = round(direct_ok_count / direct_attempt_count, 4) if direct_attempt_count > 0 else 0.0
            consecutive_failures = int(bucket.get("consecutive_failures") or 0)

            if row:
                conn.execute(
                    text(
                        """
                        UPDATE source_feed_health
                        SET updated_at = CURRENT_TIMESTAMP,
                            feed_profile_id = :feed_profile_id,
                            last_fetch_at = :last_fetch_at,
                            last_success_at = :last_success_at,
                            last_fresh_item_at = :last_fresh_item_at,
                            last_http_status = :last_http_status,
                            last_error = :last_error,
                            scraped_count_24h = :scraped_count_24h,
                            dropped_stale_count_24h = :dropped_stale_count_24h,
                            dropped_quality_count_24h = :dropped_quality_count_24h,
                            stale_ratio_24h = :stale_ratio_24h,
                            direct_ok_rate_24h = :direct_ok_rate_24h,
                            consecutive_failures = :consecutive_failures,
                            direct_attempt_count_24h = :direct_attempt_count_24h,
                            direct_ok_count_24h = :direct_ok_count_24h,
                            window_started_at = :window_started_at
                        WHERE source_code = :source_code
                          AND feed_code = :feed_code
                        """
                    ),
                    {
                        "feed_profile_id": profile["id"] if profile else row["feed_profile_id"],
                        "last_fetch_at": bucket.get("last_fetch_at"),
                        "last_success_at": bucket.get("last_success_at"),
                        "last_fresh_item_at": bucket.get("last_fresh_item_at"),
                        "last_http_status": bucket.get("last_http_status"),
                        "last_error": bucket.get("last_error"),
                        "scraped_count_24h": scraped_count,
                        "dropped_stale_count_24h": dropped_stale_count,
                        "dropped_quality_count_24h": dropped_quality_count,
                        "stale_ratio_24h": stale_ratio,
                        "direct_ok_rate_24h": direct_ok_rate,
                        "consecutive_failures": consecutive_failures,
                        "direct_attempt_count_24h": direct_attempt_count,
                        "direct_ok_count_24h": direct_ok_count,
                        "window_started_at": window_started_at,
                        "source_code": spider.source_code,
                        "feed_code": feed_code,
                    },
                )
            else:
                conn.execute(
                    text(
                        """
                        INSERT INTO source_feed_health (
                            id, created_at, updated_at, source_code, feed_code, feed_profile_id,
                            last_fetch_at, last_success_at, last_fresh_item_at, last_http_status,
                            last_error, scraped_count_24h, dropped_stale_count_24h,
                            dropped_quality_count_24h, stale_ratio_24h, direct_ok_rate_24h,
                            consecutive_failures, direct_attempt_count_24h, direct_ok_count_24h,
                            window_started_at
                        ) VALUES (
                            :id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, :source_code, :feed_code, :feed_profile_id,
                            :last_fetch_at, :last_success_at, :last_fresh_item_at, :last_http_status,
                            :last_error, :scraped_count_24h, :dropped_stale_count_24h,
                            :dropped_quality_count_24h, :stale_ratio_24h, :direct_ok_rate_24h,
                            :consecutive_failures, :direct_attempt_count_24h, :direct_ok_count_24h,
                            :window_started_at
                        )
                        """
                    ),
                    {
                        "id": str(uuid5(NAMESPACE_URL, f"globalreporter-feed-health:{spider.source_code}:{feed_code}")),
                        "source_code": spider.source_code,
                        "feed_code": feed_code,
                        "feed_profile_id": profile["id"] if profile else None,
                        "last_fetch_at": bucket.get("last_fetch_at"),
                        "last_success_at": bucket.get("last_success_at"),
                        "last_fresh_item_at": bucket.get("last_fresh_item_at"),
                        "last_http_status": bucket.get("last_http_status"),
                        "last_error": bucket.get("last_error"),
                        "scraped_count_24h": scraped_count,
                        "dropped_stale_count_24h": dropped_stale_count,
                        "dropped_quality_count_24h": dropped_quality_count,
                        "stale_ratio_24h": stale_ratio,
                        "direct_ok_rate_24h": direct_ok_rate,
                        "consecutive_failures": consecutive_failures,
                        "direct_attempt_count_24h": direct_attempt_count,
                        "direct_ok_count_24h": direct_ok_count,
                        "window_started_at": window_started_at,
                    },
                )

            if profile:
                _apply_auto_rollout_rules(
                    conn,
                    profile=profile,
                    stale_ratio=stale_ratio,
                    direct_ok_rate=direct_ok_rate,
                    consecutive_failures=consecutive_failures,
                    scraped_count=scraped_count,
                    direct_attempt_count=direct_attempt_count,
                )


def _apply_auto_rollout_rules(
    conn,
    *,
    profile: Any,
    stale_ratio: float,
    direct_ok_rate: float,
    consecutive_failures: int,
    scraped_count: int,
    direct_attempt_count: int,
) -> None:
    rollout_state = _normalize_rollout_state(profile["rollout_state"])
    enabled = bool(profile["enabled"])
    notes = str(profile["notes"] or "").strip()
    marker = None
    next_state = None
    next_enabled = enabled

    if direct_attempt_count >= 4 and direct_ok_rate < 0.25:
        next_state = "paused"
        next_enabled = False
        marker = "auto_paused_low_direct_ok"
    elif rollout_state == "default" and consecutive_failures >= 3:
        next_state = "canary"
        marker = "auto_downgraded_failures"
    elif rollout_state == "default" and scraped_count >= 4 and stale_ratio >= 0.8:
        next_state = "canary"
        marker = "auto_downgraded_stale"

    if next_state is None or (next_state == rollout_state and next_enabled == enabled):
        return

    if marker and marker not in notes:
        notes = f"{notes}; {marker}" if notes else marker

    conn.execute(
        text(
            """
            UPDATE source_feed_profiles
            SET rollout_state = :rollout_state,
                enabled = :enabled,
                notes = :notes,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = :feed_profile_id
            """
        ),
        {
            "rollout_state": next_state,
            "enabled": next_enabled,
            "notes": notes,
            "feed_profile_id": profile["id"],
        },
    )
