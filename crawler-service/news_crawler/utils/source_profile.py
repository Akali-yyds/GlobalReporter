"""Static source defaults with database-backed policy overrides."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy import create_engine, text


SOURCE_TIER_LEVEL = {
    "official": 1,
    "authoritative": 2,
    "aggregator": 3,
    "community": 3,
    "social": 4,
}

OFFICIAL_CODES = frozenset({
    "nasa_official", "openai_official", "google_blog", "youtube_official",
    "nvidia_official", "youtube_blog", "dod_official",
})
AUTHORITATIVE_CODES = frozenset({
    "bbc", "reuters", "guardian", "dw", "france24", "nhk", "cna", "scmp",
    "ndtv", "aljazeera", "global_times", "xinhua", "ap", "cnn", "ft", "npr", "unnews",
    "straits_times", "abc_news", "voa", "cbs_news", "sky_news", "nhk_world",
    "pbs_newshour", "euronews", "nbc_news", "fox_news", "times_of_india",
})
AGGREGATOR_CODES = frozenset({"google_news_cn", "google_news_en", "google_news", "gdelt_doc_global"})
SOCIAL_CODES = frozenset({"weibo", "bilibili_hot", "x_hot", "facebook_hot"})
COMMUNITY_CODES = frozenset({"github_trending", "github_releases", "github_changelog", "github_openai_releases", "reddit"})
LEAD_CODES = frozenset({
    "openai_official", "youtube_official", "github_changelog",
    "github_openai_releases", "bilibili_hot", "weibo",
    "nvidia_official", "youtube_blog", "dod_official", "gdelt_doc_global",
})
EVENT_CODES = frozenset({
    "earthquake_usgs", "disaster_gdacs", "eonet_events", "usgs", "gdacs", "eonet",
})
OFFICIAL_HOST_HINTS = (
    "openai.com", "anthropic.com", "google.com", "deepmind.google", "nasa.gov",
    "who.int", "un.org", "github.blog", "blog.google", "newsroom",
    "nvidia.com", "defense.gov", "blog.youtube",
)

_POLICY_CACHE_TTL_SECONDS = 120
_POLICY_CACHE: dict[str, tuple[float, Optional[Dict[str, Any]]]] = {}
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


def clear_source_policy_cache() -> None:
    global _ENGINE
    _POLICY_CACHE.clear()
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


def _fetch_policy_override(source_code: str) -> Optional[Dict[str, Any]]:
    now = time.time()
    cached = _POLICY_CACHE.get(source_code)
    if cached and now - cached[0] < _POLICY_CACHE_TTL_SECONDS:
        return cached[1]

    engine = _get_engine()
    if engine is None:
        _POLICY_CACHE[source_code] = (now, None)
        return None

    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT source_class, enabled, fetch_mode, schedule_minutes,
                           freshness_sla_hours, dedup_key_mode, event_time_field_priority,
                           severity_mapping_rule, geo_precision_rule, default_params_json,
                           license_mode, notes
                    FROM source_policies
                    WHERE source_code = :source_code
                    """
                ),
                {"source_code": source_code},
            ).mappings().first()
    except Exception:
        row = None

    if row is None:
        _POLICY_CACHE[source_code] = (now, None)
        return None

    policy = {
        "source_class": row["source_class"],
        "enabled": bool(row["enabled"]),
        "fetch_mode": row["fetch_mode"],
        "schedule_minutes": int(row["schedule_minutes"]),
        "freshness_sla_hours": int(row["freshness_sla_hours"]),
        "dedup_key_mode": row["dedup_key_mode"],
        "event_time_field_priority": list(_parse_json_value(row["event_time_field_priority"], [])),
        "severity_mapping_rule": row["severity_mapping_rule"],
        "geo_precision_rule": row["geo_precision_rule"],
        "default_params_json": dict(_parse_json_value(row["default_params_json"], {})),
        "license_mode": row["license_mode"],
        "notes": row["notes"],
    }
    _POLICY_CACHE[source_code] = (now, policy)
    return policy


def classify_source_tier(*, code: str, base_url: str, category: str, name: str) -> str:
    normalized_code = (code or "").strip().lower()
    normalized_url = (base_url or "").strip().lower()
    normalized_name = (name or "").strip().lower()
    normalized_category = (category or "").strip().lower()

    if normalized_code in SOCIAL_CODES or normalized_category == "social":
        return "social"
    if normalized_code in COMMUNITY_CODES or normalized_category == "community":
        return "community"
    if normalized_code in OFFICIAL_CODES:
        return "official"
    if normalized_code in AGGREGATOR_CODES:
        return "aggregator"
    if normalized_code in AUTHORITATIVE_CODES:
        return "authoritative"
    if any(hint in normalized_url for hint in OFFICIAL_HOST_HINTS):
        return "official"
    if "official" in normalized_name or normalized_category == "official":
        return "official"
    if "news.google.com" in normalized_url:
        return "aggregator"
    if "github.com" in normalized_url or "github.blog" in normalized_url:
        return "community"
    if any(host in normalized_url for host in ("x.com", "twitter.com", "weibo.com", "facebook.com", "bilibili.com")):
        return "social"
    return "authoritative"


def classify_source_class(*, code: str, base_url: str, category: str, name: str) -> str:
    normalized_code = (code or "").strip().lower()
    normalized_url = (base_url or "").strip().lower()
    normalized_name = (name or "").strip().lower()
    normalized_category = (category or "").strip().lower()

    if normalized_code in EVENT_CODES or normalized_category == "event":
        return "event"
    if normalized_code in LEAD_CODES:
        return "lead"
    if normalized_category in {"social", "community", "official", "changelog", "lead"}:
        return "lead"
    if "changelog" in normalized_name or "release" in normalized_name:
        return "lead"
    if "github.blog" in normalized_url or "/releases" in normalized_url:
        return "lead"
    return "news"


def default_freshness_sla_hours(*, source_class: str, code: str, category: str) -> int:
    normalized_code = (code or "").strip().lower()
    normalized_category = (category or "").strip().lower()
    normalized_class = (source_class or "news").strip().lower()

    if normalized_class == "event":
        if "earthquake" in normalized_code:
            return 48
        if any(token in normalized_code for token in ("gdacs", "eonet", "disaster", "wildfire", "volcano", "storm", "flood")):
            return 72
        return 72
    if normalized_class == "lead":
        if normalized_code in {"openai_official", "github_changelog", "github_openai_releases"}:
            return 168
        if normalized_code in {"youtube_official", "bilibili_hot", "weibo"}:
            return 48
        return 72
    if normalized_category in {"breaking", "live"}:
        return 12
    return 24


def default_license_mode(*, source_tier: str, source_class: str, base_url: str) -> str:
    normalized_tier = (source_tier or "").strip().lower()
    normalized_class = (source_class or "").strip().lower()
    normalized_url = (base_url or "").strip().lower()
    if normalized_class == "event":
        return "event_feed"
    if normalized_tier == "official":
        return "official_public"
    if normalized_tier == "community":
        return "community_public"
    if normalized_tier == "aggregator" or "news.google.com" in normalized_url:
        return "aggregated_public"
    if normalized_tier == "social":
        return "platform_public"
    return "publisher_public"


def resolve_source_profile(
    *,
    code: str,
    base_url: str,
    category: str,
    name: str,
    source_class: Optional[str] = None,
    freshness_sla_hours: Optional[int] = None,
    license_mode: Optional[str] = None,
) -> Dict[str, Any]:
    resolved_class = (source_class or "").strip().lower() or classify_source_class(
        code=code,
        base_url=base_url,
        category=category,
        name=name,
    )
    resolved_tier = classify_source_tier(code=code, base_url=base_url, category=category, name=name)
    resolved_tier_level = SOURCE_TIER_LEVEL.get(resolved_tier, 2)
    resolved_sla = int(freshness_sla_hours or default_freshness_sla_hours(
        source_class=resolved_class,
        code=code,
        category=category,
    ))
    resolved_license = (license_mode or "").strip().lower() or default_license_mode(
        source_tier=resolved_tier,
        source_class=resolved_class,
        base_url=base_url,
    )
    profile: Dict[str, Any] = {
        "source_class": resolved_class,
        "source_tier": resolved_tier,
        "source_tier_level": resolved_tier_level,
        "freshness_sla_hours": resolved_sla,
        "license_mode": resolved_license,
        "enabled": True,
        "fetch_mode": "poll_feed",
        "schedule_minutes": 60,
        "dedup_key_mode": "external_id" if resolved_class == "event" else "canonical_url",
        "event_time_field_priority": ["event_time", "published_at"] if resolved_class == "event" else ["published_at"],
        "severity_mapping_rule": None,
        "geo_precision_rule": "geometry" if resolved_class == "event" else "text_geo",
        "default_params_json": {},
        "notes": None,
    }

    policy = _fetch_policy_override(code)
    if not policy:
        return profile

    profile.update(
        {
            "source_class": policy["source_class"] or profile["source_class"],
            "enabled": bool(policy["enabled"]),
            "fetch_mode": policy["fetch_mode"] or profile["fetch_mode"],
            "schedule_minutes": int(policy["schedule_minutes"] or profile["schedule_minutes"]),
            "freshness_sla_hours": int(policy["freshness_sla_hours"] or profile["freshness_sla_hours"]),
            "dedup_key_mode": policy["dedup_key_mode"] or profile["dedup_key_mode"],
            "event_time_field_priority": list(policy["event_time_field_priority"] or profile["event_time_field_priority"]),
            "severity_mapping_rule": policy["severity_mapping_rule"] or profile["severity_mapping_rule"],
            "geo_precision_rule": policy["geo_precision_rule"] or profile["geo_precision_rule"],
            "default_params_json": dict(policy["default_params_json"] or profile["default_params_json"]),
            "license_mode": policy["license_mode"] or profile["license_mode"],
            "notes": policy["notes"] or profile["notes"],
        }
    )
    return profile
