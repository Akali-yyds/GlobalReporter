"""
Persist crawled articles and upsert NewsEvent rows.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy import and_, desc, or_
from sqlalchemy.orm import Session

from app.models import EventArticle, EventGeoMapping, GeoEntity, NewsArticle, NewsEvent, NewsSource
from app.services.source_strategy import SOURCE_TIER_LEVEL, resolve_source_strategy


_TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "referrer", "source", "from", "share", "via",
    "fbclid", "gclid", "msclkid", "twclid",
})
_TITLE_SOURCE_SUFFIX = re.compile(
    r"\s*[-|–—]\s*(?:bbc|reuters|ap|cnn|guardian|aljazeera|nhk|dw|france\s*24|"
    r"ndtv|scmp|cna|xinhua|global\s*times|afp|nyt|wsj|ft)\s*(?:news|world)?\s*$",
    re.IGNORECASE,
)
_TITLE_PUNCT = re.compile(r"[^\w\s\u4e00-\u9fff]")
_TITLE_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]{2,}|[a-z0-9]+")
_TITLE_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "for", "with", "from", "into", "after", "amid",
    "over", "under", "new", "latest", "says", "say", "said", "report", "reports",
    "update", "updates", "breaking", "live",
})
_EVENT_MATCH_LOOKBACK = timedelta(hours=72)
_EVENT_MATCH_MIN_SCORE = 0.84
_SOURCE_TIER_PRIORITY = {
    "official": 5,
    "authoritative": 4,
    "aggregator": 3,
    "community": 2,
    "social": 1,
}
_SOURCE_TIER_HEAT_WEIGHT = {
    "official": 18,
    "authoritative": 14,
    "aggregator": 8,
    "community": 5,
    "social": 3,
}


def _normalize_url(url: str) -> str:
    """Normalize URL for dedup: strip trailing slash, remove tracking params, lowercase scheme/host."""
    if not url:
        return url
    try:
        parsed = urlparse(url.strip())
        qs = [(k, v) for k, v in parse_qsl(parsed.query) if k.lower() not in _TRACKING_PARAMS]
        return urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/") or "/",
            parsed.params,
            urlencode(sorted(qs)),
            "",
        ))
    except Exception:
        return url


def _normalize_title_text(title: str) -> str:
    cleaned = (title or "").strip()
    cleaned = _TITLE_SOURCE_SUFFIX.sub("", cleaned)
    cleaned = _TITLE_PUNCT.sub(" ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def _normalize_title_hash(title: str) -> str:
    return hashlib.md5(_normalize_title_text(title).encode("utf-8")).hexdigest()


def _title_tokens(title: str) -> List[str]:
    tokens = _TITLE_TOKEN_RE.findall(_normalize_title_text(title))
    result: List[str] = []
    for token in tokens:
        if len(token) <= 1:
            continue
        if token in _TITLE_STOPWORDS:
            continue
        result.append(token)
    return result


def _title_similarity(left: str, right: str) -> float:
    norm_left = _normalize_title_text(left)
    norm_right = _normalize_title_text(right)
    if not norm_left or not norm_right:
        return 0.0
    if norm_left == norm_right:
        return 1.0

    compact_left = norm_left.replace(" ", "")
    compact_right = norm_right.replace(" ", "")
    seq_ratio = SequenceMatcher(None, compact_left, compact_right).ratio()

    left_tokens = set(_title_tokens(left))
    right_tokens = set(_title_tokens(right))
    token_ratio = 0.0
    if left_tokens and right_tokens:
        token_ratio = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)

    containment = 0.0
    shorter = compact_left if len(compact_left) <= len(compact_right) else compact_right
    longer = compact_right if shorter == compact_left else compact_left
    if shorter and len(shorter) >= 12 and shorter in longer:
        containment = 0.96

    return max(containment, (seq_ratio * 0.72) + (token_ratio * 0.28))


def _parse_datetime(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.astimezone(timezone.utc).replace(tzinfo=None) if val.tzinfo else val
    if isinstance(val, (int, float)):
        try:
            return datetime.fromtimestamp(int(val), tz=timezone.utc).replace(tzinfo=None)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(val, str):
        raw = val.strip()
        if not raw:
            return None
        if raw.isdigit():
            try:
                return datetime.fromtimestamp(int(raw), tz=timezone.utc).replace(tzinfo=None)
            except (OverflowError, OSError, ValueError):
                return None
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt
        except ValueError:
            pass
        try:
            return parsedate_to_datetime(raw).astimezone(timezone.utc).replace(tzinfo=None)
        except Exception:
            pass
    return None


def _normalize_tags(values: Any, *, limit: int = 20) -> List[str]:
    if not values:
        return []
    if isinstance(values, str):
        values = [values]
    normalized: List[str] = []
    for value in values:
        tag = str(value or "").strip().lower()
        if not tag or tag in normalized:
            continue
        normalized.append(tag)
        if len(normalized) >= limit:
            break
    return normalized


def _merge_tags(*groups: Any, limit: int = 20) -> List[str]:
    merged: List[str] = []
    for group in groups:
        for tag in _normalize_tags(group, limit=limit):
            if tag in merged:
                continue
            merged.append(tag)
            if len(merged) >= limit:
                return merged
    return merged


def _normalize_confidence(value: Any, *, default: int = 100) -> int:
    if value is None:
        return default
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if numeric <= 1:
        numeric *= 100
    return max(0, min(100, int(round(numeric))))


def _normalize_severity(value: Any, *, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return default


def _normalize_geo_marker(value: Any, geo_entities: List[dict]) -> Optional[str]:
    raw = str(value or "").strip().lower()
    if raw:
        return raw[:20]
    if not geo_entities:
        return None
    primary = geo_entities[0]
    geo_type = _normalize_geo_type(primary.get("type"))
    if geo_type == "city":
        return "point"
    if geo_type == "admin1":
        return "admin1"
    if geo_type == "country":
        return "country"
    return "polygon"


def _normalize_event_status(value: Any, *, source_class: str) -> str:
    normalized_class = (source_class or "news").strip().lower()
    if normalized_class != "event":
        return "closed"
    status = str(value or "").strip().lower()
    if status in {"open", "closed"}:
        return status
    if status in {"active", "ongoing"}:
        return "open"
    return "closed"


def _normalize_geometry_json(value: Any) -> Optional[dict]:
    if isinstance(value, dict):
        return value
    return None


def _normalize_bbox(value: Any) -> Optional[list[float]]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    try:
        return [float(part) for part in value]
    except (TypeError, ValueError):
        return None


def _normalize_metadata(value: Any) -> Optional[dict]:
    if isinstance(value, dict):
        return value
    return None


def _extract_point_from_geojson(value: Any) -> Optional[tuple[float, float]]:
    if not isinstance(value, dict):
        return None
    geo_type = str(value.get("type") or "").strip()
    coords = value.get("coordinates")
    if geo_type == "Point" and isinstance(coords, list) and len(coords) >= 2:
        try:
            return float(coords[1]), float(coords[0])
        except (TypeError, ValueError):
            return None
    if geo_type == "GeometryCollection":
        geometries = value.get("geometries") or []
        for geometry in geometries:
            point = _extract_point_from_geojson(geometry)
            if point:
                return point
    return None


def _extract_point_from_event(event: NewsEvent) -> Optional[tuple[float, float]]:
    return _extract_point_from_geojson(event.display_geo) or _extract_point_from_geojson(event.raw_geometry)


def _haversine_km(left: tuple[float, float], right: tuple[float, float]) -> float:
    import math

    lat1, lon1 = map(math.radians, left)
    lat2, lon2 = map(math.radians, right)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return 6371.0 * c


def _merge_source_metadata(
    existing: Optional[dict],
    incoming: Optional[dict],
    *,
    source_code: str,
    enrich_only: bool,
) -> Optional[dict]:
    if not existing and not incoming:
        return None
    merged = dict(existing or {})
    if incoming:
        if enrich_only:
            enrichment = dict(merged.get("enrichment_sources") or {})
            enrichment[source_code] = incoming
            merged["enrichment_sources"] = enrichment
            supporting_sources = list(merged.get("supporting_sources") or [])
            if source_code not in supporting_sources:
                supporting_sources.append(source_code)
            merged["supporting_sources"] = supporting_sources
        else:
            merged.update(incoming)
    return merged


def _best_source_tier(*tiers: Optional[str]) -> str:
    best = "social"
    best_priority = _SOURCE_TIER_PRIORITY[best]
    for tier in tiers:
        normalized = (tier or "").strip().lower()
        priority = _SOURCE_TIER_PRIORITY.get(normalized)
        if priority is None:
            continue
        if priority > best_priority:
            best = normalized
            best_priority = priority
    return best


def _classify_source_tier(*, code: str, base_url: str, category: str, name: str) -> str:
    normalized_code = (code or "").strip().lower()
    normalized_url = (base_url or "").strip().lower()
    normalized_name = (name or "").strip().lower()
    normalized_category = (category or "").strip().lower()

    if normalized_code in _SOCIAL_CODES or normalized_category == "social":
        return "social"
    if normalized_code in _COMMUNITY_CODES or normalized_category == "community":
        return "community"
    if normalized_code in _OFFICIAL_CODES:
        return "official"
    if normalized_code in _AGGREGATOR_CODES:
        return "aggregator"
    if normalized_code in _AUTHORITATIVE_CODES:
        return "authoritative"
    if any(hint in normalized_url for hint in _OFFICIAL_HOST_HINTS):
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


def _classify_source_class(*, code: str, base_url: str, category: str, name: str) -> str:
    normalized_code = (code or "").strip().lower()
    normalized_url = (base_url or "").strip().lower()
    normalized_name = (name or "").strip().lower()
    normalized_category = (category or "").strip().lower()

    if normalized_code in _EVENT_CODES or normalized_category == "event":
        return "event"
    if normalized_code in _LEAD_CODES:
        return "lead"
    if normalized_category in {"social", "community", "official", "changelog", "lead"}:
        return "lead"
    if "changelog" in normalized_name or "release" in normalized_name:
        return "lead"
    if "github.blog" in normalized_url or "/releases" in normalized_url:
        return "lead"
    return "news"


def _default_freshness_sla_hours(*, source_class: str, code: str, category: str) -> int:
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


def _default_license_mode(*, source_tier: str, source_class: str, base_url: str) -> str:
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


def _resolve_source_profile(
    *,
    code: str,
    base_url: str,
    category: str,
    name: str,
    source_class: Optional[str] = None,
    freshness_sla_hours: Optional[int] = None,
    license_mode: Optional[str] = None,
) -> Dict[str, Any]:
    resolved_class = (source_class or "").strip().lower() or _classify_source_class(
        code=code,
        base_url=base_url,
        category=category,
        name=name,
    )
    resolved_tier = _classify_source_tier(code=code, base_url=base_url, category=category, name=name)
    resolved_tier_level = _SOURCE_TIER_LEVEL.get(resolved_tier, 2)
    resolved_sla = int(freshness_sla_hours or _default_freshness_sla_hours(
        source_class=resolved_class,
        code=code,
        category=category,
    ))
    resolved_license = (license_mode or "").strip().lower() or _default_license_mode(
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
    }


def get_or_create_source(
    db: Session,
    *,
    name: str,
    code: str,
    base_url: str,
    country: str,
    language: str,
    category: str,
    source_class: Optional[str] = None,
    freshness_sla_hours: Optional[int] = None,
    license_mode: Optional[str] = None,
    strategy: Optional[Dict[str, Any]] = None,
) -> NewsSource:
    profile = strategy or resolve_source_strategy(
        db,
        code=code,
        base_url=base_url,
        category=category,
        name=name,
        source_class=source_class,
        freshness_sla_hours=freshness_sla_hours,
        license_mode=license_mode,
    )
    source = db.query(NewsSource).filter(NewsSource.code == code).first()
    if source:
        source.source_tier = profile["source_tier"]
        source.source_class = profile["source_class"]
        source.source_tier_level = profile["source_tier_level"]
        source.freshness_sla_hours = profile["freshness_sla_hours"]
        source.license_mode = profile["license_mode"]
        return source

    source = NewsSource(
        name=name,
        code=code,
        base_url=base_url or "https://example.com",
        country=country or "CN",
        language=language or "zh",
        category=category or "news",
        source_class=profile["source_class"],
        source_tier=profile["source_tier"],
        source_tier_level=profile["source_tier_level"],
        freshness_sla_hours=profile["freshness_sla_hours"],
        license_mode=profile["license_mode"],
        is_active=True,
    )
    db.add(source)
    db.flush()
    return source


def _normalize_geo_type(geo_type: Optional[str]) -> str:
    value = (geo_type or "").strip().lower()
    if value == "province":
        return "admin1"
    if value in {"country", "admin1", "city"}:
        return value
    return "country"


def _precision_level_from_geo_type(geo_type: str) -> str:
    if geo_type == "admin1":
        return "ADMIN1"
    if geo_type == "city":
        return "CITY"
    return "COUNTRY"


def _display_mode_from_geo_type(geo_type: str) -> str:
    return "POINT" if geo_type == "city" else "POLYGON"


def _find_existing_article(
    db: Session,
    *,
    hash_value: str,
    url: str,
    normalized_url: str,
    canonical_url: str,
    external_id: Optional[str],
    source_code: str,
    source_class: str,
) -> Optional[NewsArticle]:
    filters = [
        NewsArticle.hash == hash_value,
        NewsArticle.article_url == url,
        NewsArticle.article_url == normalized_url,
        NewsArticle.canonical_url == canonical_url,
    ]
    if external_id:
        if source_class == "event":
            filters.append(and_(NewsArticle.source_code == source_code, NewsArticle.external_id == external_id))
        else:
            filters.append(NewsArticle.external_id == external_id)
    return db.query(NewsArticle).filter(or_(*filters)).first()


def _event_similarity_score(
    *,
    title: str,
    candidate: NewsEvent,
    category: Optional[str],
    tags: List[str],
    incoming_source_tier: str,
    incoming_geo_keys: set[str],
    candidate_geo_keys: set[str],
) -> float:
    base_score = _title_similarity(title, candidate.title)
    score = base_score
    if score < 0.55:
        return 0.0

    candidate_tags = set(_normalize_tags(candidate.tags))
    overlap = len(candidate_tags & set(tags))
    if overlap:
        score += min(0.12, overlap * 0.04)
    if category and candidate.category and category == candidate.category:
        score += 0.08
    if candidate.main_country:
        score += 0.03
    geo_bonus = _geo_overlap_bonus(incoming_geo_keys, candidate_geo_keys)
    score += geo_bonus
    score += _source_tier_match_adjustment(
        incoming_source_tier=incoming_source_tier,
        candidate_source_tier=candidate.source_tier or "authoritative",
        base_score=base_score,
        geo_bonus=geo_bonus,
    )
    return min(score, 1.0)


def _find_matching_event(
    db: Session,
    *,
    title_hash: str,
    title: str,
    source_code: str,
    source_class: str,
    canonical_url: Optional[str],
    external_id: Optional[str],
    main_country: str,
    category: Optional[str],
    tags: List[str],
    incoming_source_tier: str,
    incoming_geo_keys: List[str],
    event_time: Optional[datetime],
    incoming_point: Optional[tuple[float, float]],
    now: datetime,
) -> Optional[NewsEvent]:
    normalized_source_code = (source_code or "").strip().lower()
    if normalized_source_code == "disaster_gdacs":
        if external_id:
            exact_external = (
                db.query(NewsEvent)
                .filter(
                    NewsEvent.source_code == normalized_source_code,
                    NewsEvent.external_id == external_id,
                )
                .first()
            )
            if exact_external:
                return exact_external
        return _find_gdacs_enrichment_target(
            db,
            main_country=main_country,
            event_time=event_time,
            incoming_point=incoming_point,
            tags=tags,
            now=now,
        )
    if source_class == "event":
        if external_id:
            exact_external = (
                db.query(NewsEvent)
                .filter(
                    NewsEvent.source_code == normalized_source_code,
                    NewsEvent.external_id == external_id,
                )
                .first()
            )
            if exact_external:
                return exact_external
        if canonical_url:
            exact_canonical = (
                db.query(NewsEvent)
                .filter(
                    NewsEvent.source_code == normalized_source_code,
                    NewsEvent.canonical_url == canonical_url,
                )
                .first()
            )
            if exact_canonical:
                return exact_canonical
        return None

    if external_id:
        exact_external = db.query(NewsEvent).filter(NewsEvent.external_id == external_id).first()
        if exact_external:
            return exact_external

    exact = db.query(NewsEvent).filter(NewsEvent.title_hash == title_hash).first()
    if exact:
        return exact

    cutoff = now - _EVENT_MATCH_LOOKBACK
    query = db.query(NewsEvent).filter(NewsEvent.last_seen_at >= cutoff)
    if main_country:
        query = query.filter(NewsEvent.main_country == main_country)
    candidates = query.order_by(desc(NewsEvent.last_seen_at)).limit(80).all()
    geo_map = _load_event_geo_key_map(db, [candidate.id for candidate in candidates])
    normalized_incoming_geo_keys = {value for value in incoming_geo_keys if value}

    best_event: Optional[NewsEvent] = None
    best_score = 0.0
    for candidate in candidates:
        score = _event_similarity_score(
            title=title,
            candidate=candidate,
            category=category,
            tags=tags,
            incoming_source_tier=incoming_source_tier,
            incoming_geo_keys=normalized_incoming_geo_keys,
            candidate_geo_keys=geo_map.get(candidate.id, set()),
        )
        if score > best_score:
            best_score = score
            best_event = candidate

    return best_event if best_score >= _EVENT_MATCH_MIN_SCORE else None


def _find_gdacs_enrichment_target(
    db: Session,
    *,
    main_country: str,
    event_time: Optional[datetime],
    incoming_point: Optional[tuple[float, float]],
    tags: List[str],
    now: datetime,
) -> Optional[NewsEvent]:
    cutoff = now - timedelta(days=7)
    query = db.query(NewsEvent).filter(NewsEvent.last_seen_at >= cutoff)
    if main_country:
        query = query.filter(NewsEvent.main_country == main_country)
    candidates = query.order_by(desc(NewsEvent.last_seen_at)).limit(100).all()
    incoming_tags = set(tags)

    best: Optional[NewsEvent] = None
    best_score = 0.0
    for candidate in candidates:
        if (candidate.source_code or "").strip().lower() == "disaster_gdacs":
            continue
        candidate_tags = set(_normalize_tags(candidate.tags))
        if incoming_tags and candidate_tags and not (incoming_tags & candidate_tags):
            continue
        score = 0.0
        if event_time and candidate.event_time:
            delta_hours = abs((candidate.event_time - event_time).total_seconds()) / 3600.0
            if delta_hours <= 12:
                score += 0.45
            elif delta_hours <= 48:
                score += 0.28
            elif delta_hours <= 120:
                score += 0.12
        if incoming_tags & candidate_tags:
            score += 0.25

        candidate_point = _extract_point_from_event(candidate)
        if incoming_point and candidate_point:
            distance_km = _haversine_km(incoming_point, candidate_point)
            if distance_km <= 150:
                score += 0.35
            elif distance_km <= 500:
                score += 0.22
            elif distance_km <= 1200:
                score += 0.08
        elif incoming_point is None:
            score += 0.08

        if candidate.category == "disaster":
            score += 0.08
        if score > best_score:
            best_score = score
            best = candidate

    return best if best_score >= 0.45 else None


def _latest_signal_time(*values: Optional[datetime]) -> Optional[datetime]:
    present = [value for value in values if value is not None]
    return max(present) if present else None


def _load_event_geo_key_map(db: Session, event_ids: List[str]) -> Dict[str, set[str]]:
    if not event_ids:
        return {}
    rows = (
        db.query(EventGeoMapping.event_id, EventGeoMapping.geo_key)
        .filter(EventGeoMapping.event_id.in_(event_ids))
        .all()
    )
    mapping: Dict[str, set[str]] = {event_id: set() for event_id in event_ids}
    for event_id, geo_key in rows:
        if event_id and geo_key:
            mapping.setdefault(event_id, set()).add(geo_key)
    return mapping


def _geo_overlap_bonus(incoming_geo_keys: set[str], candidate_geo_keys: set[str]) -> float:
    if not incoming_geo_keys or not candidate_geo_keys:
        return 0.0
    if incoming_geo_keys & candidate_geo_keys:
        return 0.14
    for incoming_key in incoming_geo_keys:
        for candidate_key in candidate_geo_keys:
            if incoming_key.startswith(candidate_key) or candidate_key.startswith(incoming_key):
                return 0.08

    incoming_countries = {value.split(":", 1)[0] for value in incoming_geo_keys if ":" in value}
    candidate_countries = {value.split(":", 1)[0] for value in candidate_geo_keys if ":" in value}
    if incoming_countries and incoming_countries & candidate_countries:
        return -0.24
    return 0.0


def _source_tier_match_adjustment(
    *,
    incoming_source_tier: str,
    candidate_source_tier: str,
    base_score: float,
    geo_bonus: float,
) -> float:
    incoming = (incoming_source_tier or "authoritative").strip().lower()
    candidate = (candidate_source_tier or "authoritative").strip().lower()
    incoming_priority = _SOURCE_TIER_PRIORITY.get(incoming, _SOURCE_TIER_PRIORITY["social"])
    candidate_priority = _SOURCE_TIER_PRIORITY.get(candidate, _SOURCE_TIER_PRIORITY["social"])
    distance = abs(incoming_priority - candidate_priority)

    if incoming == candidate:
        return 0.04
    if distance >= 3 and base_score < 0.95 and geo_bonus < 0.10:
        return -0.12
    if distance == 2 and base_score < 0.92 and geo_bonus < 0.10:
        return -0.06
    if incoming_priority >= 4 and candidate_priority >= 4:
        return 0.02
    return 0.0


def _topic_heat_bonus(category: Optional[str], tags: List[str]) -> int:
    score = 0
    tag_set = set(tags)
    if tag_set & {"ai", "chip", "cybersecurity", "conflict", "disaster", "protest"}:
        score += 12
    if tag_set & {"science", "space", "climate", "policy", "economy", "health", "energy", "diplomacy", "transport", "crime"}:
        score += 8
    if category in {"technology", "science", "conflict", "disaster"}:
        score += 6
    elif category in {"policy", "business"}:
        score += 4
    return min(score, 20)


def _event_level_heat_bonus(event_level: str) -> int:
    if event_level == "city":
        return 8
    if event_level == "admin1":
        return 4
    return 0


def _recency_heat_bonus(signal_time: Optional[datetime], now: datetime) -> int:
    if signal_time is None:
        return 0
    age = now - signal_time
    if age <= timedelta(hours=6):
        return 18
    if age <= timedelta(hours=24):
        return 12
    if age <= timedelta(hours=72):
        return 6
    return 0


def _load_event_article_signals(db: Session, event_id: str) -> List[tuple[int, str, str, Optional[datetime]]]:
    rows = (
        db.query(
            NewsArticle.heat_score,
            NewsArticle.source_code,
            NewsSource.source_tier,
            NewsArticle.publish_time,
            NewsArticle.crawl_time,
        )
        .join(EventArticle, EventArticle.article_id == NewsArticle.id)
        .join(NewsSource, NewsSource.id == NewsArticle.source_id)
        .filter(EventArticle.event_id == event_id)
        .all()
    )
    return [
        (
            int(heat_score or 0),
            source_code or "unknown",
            source_tier or "authoritative",
            _latest_signal_time(publish_time, crawl_time),
        )
        for heat_score, source_code, source_tier, publish_time, crawl_time in rows
    ]


def _compute_event_heat(
    *,
    db: Session,
    event: NewsEvent,
    incoming_heat: int,
    incoming_source_code: str,
    incoming_source_tier: str,
    incoming_signal_time: Optional[datetime],
    merged_tags: List[str],
    now: datetime,
) -> int:
    historical = _load_event_article_signals(db, event.id) if event.id else []
    heat_scores = [score for score, _source, _tier, _dt in historical]
    source_codes = {source for _score, source, _tier, _dt in historical if source}
    source_tiers = [_tier for _score, _source, _tier, _dt in historical if _tier]
    signal_times = [dt for _score, _source, _tier, dt in historical if dt is not None]

    heat_scores.append(max(incoming_heat, 1))
    source_codes.add(incoming_source_code or "unknown")
    source_tiers.append(incoming_source_tier or "authoritative")
    if incoming_signal_time is not None:
        signal_times.append(incoming_signal_time)

    article_count = max(event.article_count or 0, len(heat_scores))
    source_count = max(1, len(source_codes))
    primary_heat = max(heat_scores) if heat_scores else 1
    avg_heat = int(round(sum(heat_scores) / len(heat_scores))) if heat_scores else primary_heat

    signal_score = int(primary_heat * 0.62 + avg_heat * 0.38)
    article_bonus = min(42, article_count * 6)
    source_bonus = min(36, source_count * 9)
    best_tier = _best_source_tier(*source_tiers)
    tier_bonus = _SOURCE_TIER_HEAT_WEIGHT.get(best_tier, 0)
    topic_bonus = _topic_heat_bonus(event.category, merged_tags)
    geo_bonus = _event_level_heat_bonus(event.event_level or "country")
    recency_bonus = _recency_heat_bonus(max(signal_times) if signal_times else None, now)
    severity_bonus = min(24, int(round((event.severity or 0) * 0.24)))

    return min(
        9999,
        max(1, signal_score + article_bonus + source_bonus + tier_bonus + topic_bonus + geo_bonus + recency_bonus + severity_bonus),
    )


def _get_or_create_geo_entity(db: Session, payload: Dict[str, Any]) -> GeoEntity:
    geo_key = (payload.get("geo_key") or "").strip()[:20]
    geo = db.query(GeoEntity).filter(GeoEntity.geo_key == geo_key).first()
    if geo:
        if geo.lat is None and payload.get("lat") is not None:
            geo.lat = payload.get("lat")
        if geo.lng is None and payload.get("lng") is not None:
            geo.lng = payload.get("lng")
        if not geo.geojson_key and payload.get("geojson_key"):
            geo.geojson_key = payload.get("geojson_key")
        if not geo.display_mode and payload.get("display_mode"):
            geo.display_mode = payload.get("display_mode")
        if not geo.precision_level and payload.get("precision_level"):
            geo.precision_level = payload.get("precision_level")
        return geo

    geo = GeoEntity(
        name=(payload.get("name") or payload.get("country_name") or payload.get("admin1_name") or payload.get("city_name") or geo_key)[:100],
        geo_key=geo_key,
        country_code=(payload.get("country_code") or geo_key.split("_")[0] or "UNKNOWN")[:10],
        country_name=payload.get("country_name") or None,
        admin1_code=payload.get("admin1_code") or None,
        admin1_name=payload.get("admin1_name") or None,
        city_name=payload.get("city_name") or None,
        precision_level=(payload.get("precision_level") or _precision_level_from_geo_type(_normalize_geo_type(payload.get("type"))))[:20],
        display_mode=(payload.get("display_mode") or _display_mode_from_geo_type(_normalize_geo_type(payload.get("type"))))[:20],
        geojson_key=(payload.get("geojson_key") or geo_key)[:100],
        lat=payload.get("lat"),
        lng=payload.get("lng"),
        is_active=True,
    )
    db.add(geo)
    db.flush()
    return geo


def _sync_event_geo_mappings(db: Session, event: NewsEvent, raw_geo_entities: List[dict]) -> None:
    if not raw_geo_entities:
        return

    existing = {
        mapping.geo_key: mapping
        for mapping in db.query(EventGeoMapping).filter(EventGeoMapping.event_id == event.id).all()
    }

    seen_geo_keys: set[str] = set()
    for idx, payload in enumerate(raw_geo_entities):
        geo_key = (payload.get("geo_key") or "").strip()[:20]
        if not geo_key or geo_key in seen_geo_keys:
            continue
        seen_geo_keys.add(geo_key)

        geo = _get_or_create_geo_entity(db, payload)
        mapping = existing.get(geo_key)
        if mapping is None:
            mapping = EventGeoMapping(
                event_id=event.id,
                geo_id=geo.id,
                geo_key=geo_key,
            )
            db.add(mapping)

        mapping.geo_id = geo.id
        mapping.matched_text = (payload.get("matched_text") or payload.get("name") or geo.name or geo_key)[:500]
        has_text_scan = bool(payload.get("matched_text")) or bool(payload.get("source_text_position"))
        mapping.extraction_method = "dictionary_match+text_scan" if has_text_scan else "dictionary_match"
        mapping.confidence = float(payload.get("confidence") or 1.0)
        relevance_score = payload.get("relevance_score")
        mapping.relevance_score = float(relevance_score) if relevance_score is not None else (1.0 if idx == 0 else 0.8)
        mapping.is_primary = bool(payload.get("is_primary")) if payload.get("is_primary") is not None else idx == 0
        mapping.source_text_position = payload.get("source_text_position") or ("title" if idx == 0 else None)


def ingest_crawled_articles(db: Session, items: List[dict]) -> dict:
    """Insert or update articles and events used by the API."""
    created_articles = 0
    skipped = 0
    events_touched = 0

    for raw in items:
        title = (raw.get("title") or "").strip()
        url = (raw.get("url") or "").strip()
        hash_value = (raw.get("hash") or raw.get("content_hash") or "").strip()
        if not title or not url or not hash_value:
            skipped += 1
            continue

        normalized_url = _normalize_url(url)
        canonical_url = (raw.get("canonical_url") or normalized_url or url).strip()
        external_id = str(raw.get("external_id") or "").strip() or None
        raw_source_code = (raw.get("source_code") or "unknown").strip().lower()
        strategy = resolve_source_strategy(
            db,
            code=raw_source_code,
            base_url=raw.get("source_url") or url,
            category=raw.get("category") or "news",
            name=raw.get("source_name") or "Unknown",
            source_class=raw.get("source_class"),
            freshness_sla_hours=raw.get("freshness_sla_hours"),
            license_mode=raw.get("license_mode"),
        )
        if not strategy.get("enabled", True):
            skipped += 1
            continue
        source_class = (raw.get("source_class") or strategy["source_class"] or "news").strip().lower()
        duplicate = _find_existing_article(
            db,
            hash_value=hash_value,
            url=url,
            normalized_url=normalized_url,
            canonical_url=canonical_url,
            external_id=external_id,
            source_code=raw_source_code,
            source_class=source_class,
        )
        if duplicate and source_class != "event":
            skipped += 1
            continue

        source = get_or_create_source(
            db,
            name=raw.get("source_name") or "Unknown",
            code=raw_source_code,
            base_url=raw.get("source_url") or url,
            country=raw.get("country") or "CN",
            language=raw.get("language") or "zh",
            category=raw.get("category") or "news",
            source_class=raw.get("source_class"),
            freshness_sla_hours=raw.get("freshness_sla_hours"),
            license_mode=raw.get("license_mode"),
            strategy=strategy,
        )
        source_tier = source.source_tier or "authoritative"
        source_class = (raw.get("source_class") or strategy["source_class"] or source.source_class or "news").strip().lower()
        source_tier_level = int(raw.get("source_tier_level") or source.source_tier_level or _SOURCE_TIER_LEVEL.get(source_tier, 2))
        freshness_sla_hours = int(raw.get("freshness_sla_hours") or strategy["freshness_sla_hours"] or source.freshness_sla_hours or 24)
        license_mode = (raw.get("license_mode") or strategy["license_mode"] or source.license_mode or "public_web").strip().lower()

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        crawl_time = _parse_datetime(raw.get("crawled_at")) or now
        publish_time = _parse_datetime(raw.get("published_at"))
        event_time = _parse_datetime(raw.get("event_time"))
        event_status = _normalize_event_status(raw.get("event_status"), source_class=source_class)
        closed_at = _parse_datetime(raw.get("closed_at"))
        source_updated_at = _parse_datetime(raw.get("source_updated_at"))
        signal_time = _latest_signal_time(source_updated_at, closed_at, event_time, publish_time, crawl_time)

        tags = _normalize_tags(raw.get("tags"))
        region_tags = raw.get("region_tags") or []
        if isinstance(region_tags, str):
            region_tags = [region_tags]
        region_tags = [str(value).strip() for value in region_tags if value][:30]

        raw_geo_entities = raw.get("geo_entities") or []
        if not isinstance(raw_geo_entities, list):
            raw_geo_entities = []
        geo_marker = _normalize_geo_marker(raw.get("geo"), raw_geo_entities)
        geom_type = str(raw.get("geom_type") or "").strip() or None
        raw_geometry = _normalize_geometry_json(raw.get("raw_geometry"))
        display_geo = _normalize_geometry_json(raw.get("display_geo"))
        bbox = _normalize_bbox(raw.get("bbox"))
        source_metadata = _normalize_metadata(raw.get("source_metadata"))
        incoming_point = _extract_point_from_geojson(display_geo) or _extract_point_from_geojson(raw_geometry)
        if display_geo and not geom_type:
            geom_type = str(display_geo.get("type") or "").strip() or None
        severity = _normalize_severity(raw.get("severity"))
        confidence = _normalize_confidence(raw.get("confidence"))
        canonical_url = canonical_url[:2000]
        external_id = external_id[:255] if external_id else None

        main_country = ""
        event_level = "country"
        if raw_geo_entities:
            primary_geo = raw_geo_entities[0]
            main_country = (primary_geo.get("country_code") or "")[:10]
            event_level = (_normalize_geo_type(primary_geo.get("type")) or "country")[:20]
        if region_tags:
            main_country = region_tags[0][:10]
        if not main_country:
            main_country = (raw.get("country") or "CN")[:10]

        article_created = duplicate is None
        if duplicate is None:
            article = NewsArticle(
                title=title[:500],
                summary=raw.get("summary") or None,
                content=raw.get("content") or None,
                article_url=url[:2000],
                source_id=source.id,
                source_name=source.name,
                source_code=source.code,
                source_url=source.base_url,
                source_class=source_class,
                publish_time=publish_time,
                event_time=event_time,
                crawl_time=crawl_time,
                freshness_sla_hours=freshness_sla_hours,
                heat_score=int(raw.get("heat_score") or 0),
                severity=severity,
                confidence=confidence,
                category=raw.get("category") or None,
                language=(raw.get("language") or "zh")[:10],
                geo=geo_marker,
                geom_type=geom_type,
                raw_geometry=raw_geometry,
                display_geo=display_geo,
                bbox=bbox,
                source_metadata=source_metadata,
                license_mode=license_mode,
                canonical_url=canonical_url,
                external_id=external_id,
                country_tags=[raw.get("country")] if raw.get("country") else [],
                city_tags=[],
                region_tags=region_tags,
                tags=tags,
                hash=hash_value[:64],
            )
            db.add(article)
            db.flush()
        else:
            article = duplicate
            article.title = title[:500]
            article.summary = raw.get("summary") or None
            article.content = raw.get("content") or None
            article.article_url = url[:2000]
            article.source_id = source.id
            article.source_name = source.name
            article.source_code = source.code
            article.source_url = source.base_url
            article.source_class = source_class
            article.publish_time = publish_time
            article.event_time = event_time
            article.crawl_time = crawl_time
            article.freshness_sla_hours = freshness_sla_hours
            article.heat_score = int(raw.get("heat_score") or 0)
            article.severity = severity
            article.confidence = confidence
            article.category = raw.get("category") or None
            article.language = (raw.get("language") or "zh")[:10]
            article.geo = geo_marker
            article.geom_type = geom_type
            article.raw_geometry = raw_geometry
            article.display_geo = display_geo
            article.bbox = bbox
            article.source_metadata = source_metadata
            article.license_mode = license_mode
            article.canonical_url = canonical_url
            article.external_id = external_id
            article.country_tags = [raw.get("country")] if raw.get("country") else []
            article.city_tags = []
            article.region_tags = region_tags
            article.tags = tags
            article.hash = hash_value[:64]

        title_hash = _normalize_title_hash(title)
        summary = (raw.get("summary") or "")[:2000] if raw.get("summary") else None
        incoming_heat = int(raw.get("heat_score") or 0)
        category = raw.get("category") or None

        event = _find_matching_event(
            db,
            title_hash=title_hash,
            title=title,
            source_code=source.code,
            source_class=source_class,
            canonical_url=canonical_url,
            external_id=external_id,
            main_country=main_country,
            category=category,
            tags=tags,
            incoming_source_tier=source_tier,
            incoming_geo_keys=[
                str(payload.get("geo_key") or "").strip()
                for payload in raw_geo_entities
                if isinstance(payload, dict)
            ],
            event_time=event_time,
            incoming_point=incoming_point,
            now=now,
        )
        is_new_event = event is None
        existing_link = None
        is_enrichment_update = source.code == "disaster_gdacs" and event is not None and (event.source_code or "") != source.code

        if event:
            event.last_seen_at = now
            existing_link = (
                db.query(EventArticle)
                .filter(EventArticle.event_id == event.id, EventArticle.article_id == article.id)
                .first()
            )
            if existing_link is None:
                event.article_count = (event.article_count or 0) + 1
            if not event.main_country and main_country:
                event.main_country = main_country
            if event_level in {"admin1", "city"} and event.event_level == "country":
                event.event_level = event_level
            if summary and (not event.summary or len(summary) > len(event.summary)):
                event.summary = summary
            if not event.category and category:
                event.category = category
            merged_tags = _merge_tags(event.tags, tags)
            event.tags = merged_tags
            event.source_class = source_class or event.source_class
            if (source_class == "event" and not is_enrichment_update) or not event.source_code:
                event.source_code = source.code
            if not is_enrichment_update:
                event.source_tier = _best_source_tier(event.source_tier, source_tier)
                event.source_tier_level = min(event.source_tier_level or source_tier_level, source_tier_level)
            event.freshness_sla_hours = max(event.freshness_sla_hours or freshness_sla_hours, freshness_sla_hours)
            event.event_time = _latest_signal_time(event.event_time, event_time)
            event.source_updated_at = _latest_signal_time(event.source_updated_at, source_updated_at)
            if source_class == "event":
                if not is_enrichment_update or event.event_status != "open":
                    event.event_status = event_status
                if not is_enrichment_update:
                    event.closed_at = None if event_status == "open" else _latest_signal_time(event.closed_at, closed_at, event_time)
                elif event_status != "open":
                    event.closed_at = _latest_signal_time(event.closed_at, closed_at, event_time)
            event.severity = max(event.severity or 0, severity)
            event.confidence = max(event.confidence or 0, confidence)
            event.geo = event.geo or geo_marker
            if source_class == "event":
                if not is_enrichment_update:
                    event.geom_type = geom_type or event.geom_type
                    event.raw_geometry = raw_geometry or event.raw_geometry
                    event.display_geo = display_geo or event.display_geo
                    event.bbox = bbox or event.bbox
            else:
                event.geom_type = event.geom_type or geom_type
                event.raw_geometry = event.raw_geometry or raw_geometry
                event.display_geo = event.display_geo or display_geo
                event.bbox = event.bbox or bbox
            event.source_metadata = _merge_source_metadata(
                event.source_metadata,
                source_metadata,
                source_code=source.code,
                enrich_only=is_enrichment_update,
            )
            event.license_mode = (
                event.license_mode if is_enrichment_update else
                (license_mode if source_class == "event" else (event.license_mode or license_mode))
            )
            if canonical_url and ((source_class == "event" and not is_enrichment_update) or not event.canonical_url):
                event.canonical_url = canonical_url
            if external_id and ((source_class == "event" and not is_enrichment_update) or not event.external_id):
                event.external_id = external_id
            event.heat_score = _compute_event_heat(
                db=db,
                event=event,
                incoming_heat=incoming_heat,
                incoming_source_code=source.code,
                incoming_source_tier=source_tier,
                incoming_signal_time=signal_time,
                merged_tags=merged_tags,
                now=now,
            )
            events_touched += 1
        else:
            event = NewsEvent(
                title=title[:500],
                summary=summary,
                main_country=main_country,
                event_level=event_level,
                source_code=source.code,
                source_class=source_class,
                heat_score=1,
                severity=severity,
                confidence=confidence,
                article_count=1,
                category=category,
                geo=geo_marker,
                geom_type=geom_type,
                raw_geometry=raw_geometry,
                display_geo=display_geo,
                bbox=bbox,
                source_metadata=source_metadata,
                tags=tags,
                source_tier=source_tier,
                source_tier_level=source_tier_level,
                freshness_sla_hours=freshness_sla_hours,
                event_time=event_time,
                event_status=event_status,
                closed_at=None if event_status == "open" else _latest_signal_time(closed_at, event_time),
                source_updated_at=source_updated_at,
                license_mode=license_mode,
                canonical_url=canonical_url,
                external_id=external_id,
                title_hash=title_hash,
                first_seen_at=now,
                last_seen_at=now,
            )
            db.add(event)
            db.flush()
            event.heat_score = _compute_event_heat(
                db=db,
                event=event,
                incoming_heat=incoming_heat,
                incoming_source_code=source.code,
                incoming_source_tier=source_tier,
                incoming_signal_time=signal_time,
                merged_tags=tags,
                now=now,
            )
            events_touched += 1

        if existing_link is None:
            link = EventArticle(event_id=event.id, article_id=article.id, is_primary=is_new_event)
            db.add(link)
        _sync_event_geo_mappings(db, event, raw_geo_entities)

        if article_created:
            created_articles += 1

    db.commit()
    return {
        "created_articles": created_articles,
        "skipped_duplicates": skipped,
        "events_touched": events_touched,
    }
