"""Static defaults + database policy overrides for source behavior."""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models import SourcePolicy


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


def _static_defaults(
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
    return {
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


def resolve_source_strategy(
    db: Session,
    *,
    code: str,
    base_url: str,
    category: str,
    name: str,
    source_class: Optional[str] = None,
    freshness_sla_hours: Optional[int] = None,
    license_mode: Optional[str] = None,
) -> Dict[str, Any]:
    strategy = _static_defaults(
        code=code,
        base_url=base_url,
        category=category,
        name=name,
        source_class=source_class,
        freshness_sla_hours=freshness_sla_hours,
        license_mode=license_mode,
    )

    policy = db.query(SourcePolicy).filter(SourcePolicy.source_code == code).first()
    if not policy:
        return strategy

    strategy.update(
        {
            "source_class": policy.source_class or strategy["source_class"],
            "enabled": bool(policy.enabled),
            "fetch_mode": policy.fetch_mode or strategy["fetch_mode"],
            "schedule_minutes": int(policy.schedule_minutes or strategy["schedule_minutes"]),
            "freshness_sla_hours": int(policy.freshness_sla_hours or strategy["freshness_sla_hours"]),
            "dedup_key_mode": policy.dedup_key_mode or strategy["dedup_key_mode"],
            "event_time_field_priority": list(policy.event_time_field_priority or strategy["event_time_field_priority"]),
            "severity_mapping_rule": policy.severity_mapping_rule or strategy["severity_mapping_rule"],
            "geo_precision_rule": policy.geo_precision_rule or strategy["geo_precision_rule"],
            "default_params_json": dict(policy.default_params_json or strategy["default_params_json"]),
            "license_mode": policy.license_mode or strategy["license_mode"],
            "notes": policy.notes or strategy["notes"],
        }
    )
    return strategy
