"""Database-backed job profile and checkpoint helpers for event crawlers."""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy import create_engine, text


_CACHE_TTL_SECONDS = 120
_PROFILE_CACHE: dict[str, tuple[float, Optional[Dict[str, Any]]]] = {}
_ENGINE = None


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


def clear_source_job_profile_cache() -> None:
    global _ENGINE
    _PROFILE_CACHE.clear()
    if _ENGINE is not None:
        _ENGINE.dispose()
        _ENGINE = None


def _parse_json_value(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return default


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def resolve_source_job_profile(job_name: str, fallback: Dict[str, Any]) -> Dict[str, Any]:
    now = time.time()
    cached = _PROFILE_CACHE.get(job_name)
    if cached and now - cached[0] < _CACHE_TTL_SECONDS and cached[1] is not None:
        merged = dict(fallback)
        merged.update(cached[1])
        return merged

    engine = _get_engine()
    if engine is None:
        return dict(fallback)

    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT source_code, source_class, job_mode, window_mode, cursor_strategy,
                           enabled, schedule_minutes, priority, default_params_json, notes
                    FROM source_job_profiles
                    WHERE job_name = :job_name
                    """
                ),
                {"job_name": job_name},
            ).mappings().first()
    except Exception:
        row = None

    if row is None:
        _PROFILE_CACHE[job_name] = (now, None)
        return dict(fallback)

    profile = {
        "source_code": row["source_code"],
        "source_class": row["source_class"],
        "job_mode": row["job_mode"],
        "window_mode": row["window_mode"],
        "cursor_strategy": row["cursor_strategy"],
        "enabled": bool(row["enabled"]),
        "schedule_minutes": int(row["schedule_minutes"]),
        "priority": int(row["priority"]),
        "default_params_json": dict(_parse_json_value(row["default_params_json"], {})),
        "notes": row["notes"],
    }
    _PROFILE_CACHE[job_name] = (now, profile)
    merged = dict(fallback)
    merged.update(profile)
    return merged


def resolve_source_job_checkpoint(job_name: str) -> Optional[Dict[str, Any]]:
    engine = _get_engine()
    if engine is None:
        return None

    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT job_name, source_code, job_mode, last_success_at,
                           last_seen_external_id, last_seen_source_updated_at, last_event_time,
                           last_seen_page, last_query_window
                    FROM source_job_checkpoints
                    WHERE job_name = :job_name
                    """
                ),
                {"job_name": job_name},
            ).mappings().first()
    except Exception:
        row = None

    if row is None:
        return None

    return {
        "job_name": row["job_name"],
        "source_code": row["source_code"],
        "job_mode": row["job_mode"],
        "last_success_at": row["last_success_at"],
        "last_seen_external_id": row["last_seen_external_id"],
        "last_seen_source_updated_at": row["last_seen_source_updated_at"],
        "last_event_time": row["last_event_time"],
        "last_seen_page": row.get("last_seen_page"),
        "last_query_window": _parse_json_value(row.get("last_query_window"), None),
    }


def update_source_job_checkpoint(
    *,
    job_name: str,
    source_code: str,
    job_mode: str,
    last_success_at: Optional[str],
    last_seen_external_id: Optional[str],
    last_seen_source_updated_at: Optional[str],
    last_event_time: Optional[str],
    last_seen_page: Optional[int] = None,
    last_query_window: Optional[Dict[str, Any]] = None,
) -> None:
    engine = _get_engine()
    if engine is None:
        return

    with engine.begin() as conn:
        existing = conn.execute(
            text("SELECT id FROM source_job_checkpoints WHERE job_name = :job_name"),
            {"job_name": job_name},
        ).mappings().first()
        params = {
            "job_name": job_name,
            "source_code": source_code,
            "job_mode": job_mode,
            "last_success_at": _parse_datetime(last_success_at),
            "last_seen_external_id": last_seen_external_id,
            "last_seen_source_updated_at": _parse_datetime(last_seen_source_updated_at),
            "last_event_time": _parse_datetime(last_event_time),
            "last_seen_page": last_seen_page,
            "last_query_window": json.dumps(last_query_window) if last_query_window is not None else None,
        }
        if existing:
            conn.execute(
                text(
                    """
                    UPDATE source_job_checkpoints
                    SET source_code = :source_code,
                        job_mode = :job_mode,
                        last_success_at = :last_success_at,
                        last_seen_external_id = :last_seen_external_id,
                        last_seen_source_updated_at = :last_seen_source_updated_at,
                        last_event_time = :last_event_time,
                        last_seen_page = :last_seen_page,
                        last_query_window = :last_query_window,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE job_name = :job_name
                    """
                ),
                params,
            )
        else:
            conn.execute(
                text(
                    """
                        INSERT INTO source_job_checkpoints (
                        id, job_name, source_code, job_mode, last_success_at,
                        last_seen_external_id, last_seen_source_updated_at,
                        last_event_time, last_seen_page, last_query_window, created_at, updated_at
                    ) VALUES (
                        :id, :job_name, :source_code, :job_mode, :last_success_at,
                        :last_seen_external_id, :last_seen_source_updated_at, :last_event_time,
                        :last_seen_page, :last_query_window,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    """
                ),
                {"id": str(uuid.uuid4()), **params},
            )
