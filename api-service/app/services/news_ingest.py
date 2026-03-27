"""
Persist crawled articles and upsert NewsEvent rows (used by /api/news/hot).
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urlencode, parse_qsl, urlunparse

from sqlalchemy.orm import Session

from app.models import EventArticle, EventGeoMapping, GeoEntity, NewsArticle, NewsEvent, NewsSource


_TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "referrer", "source", "from", "share", "via",
    "fbclid", "gclid", "msclkid", "twclid",
})


def _normalize_url(url: str) -> str:
    """Normalize URL for dedup: strip trailing slash, remove tracking params, lowercase scheme/host."""
    if not url:
        return url
    try:
        p = urlparse(url.strip())
        qs = [(k, v) for k, v in parse_qsl(p.query) if k.lower() not in _TRACKING_PARAMS]
        normalized = urlunparse((
            p.scheme.lower(),
            p.netloc.lower(),
            p.path.rstrip("/") or "/",
            p.params,
            urlencode(sorted(qs)),
            "",  # drop fragment
        ))
        return normalized
    except Exception:
        return url


_TITLE_SOURCE_SUFFIX = re.compile(
    r"\s*[-|–—]\s*(?:bbc|reuters|ap|cnn|guardian|aljazeera|nhk|dw|france\s*24|"
    r"ndtv|scmp|cna|xinhua|global\s*times|afp|nyt|wsj|ft)\s*(?:news|world)?\s*$",
    re.IGNORECASE,
)
_TITLE_PUNCT = re.compile(r"[^\w\s\u4e00-\u9fff]")


def _normalize_title_hash(title: str) -> str:
    """Stable hash for event dedup — strips source suffixes and punctuation (works with CJK)."""
    t = (title or "").strip()
    t = _TITLE_SOURCE_SUFFIX.sub("", t)
    t = _TITLE_PUNCT.sub(" ", t)
    t = re.sub(r"\s+", " ", t).strip().lower()
    return hashlib.md5(t.encode("utf-8")).hexdigest()


def _parse_datetime(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.replace(tzinfo=None) if val.tzinfo else val
    if isinstance(val, (int, float)):
        try:
            return datetime.utcfromtimestamp(int(val))
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return None
        if s.isdigit():
            try:
                return datetime.utcfromtimestamp(int(s))
            except (OverflowError, OSError, ValueError):
                return None
        # ISO 8601 (handles "2026-03-25T08:00:00+08:00", "Z")
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt
        except ValueError:
            pass
        # RFC 2822 (RSS feeds: "Tue, 25 Mar 2026 08:00:00 +0800")
        try:
            return parsedate_to_datetime(s).astimezone(timezone.utc).replace(tzinfo=None)
        except Exception:
            pass
    return None


def get_or_create_source(
    db: Session,
    *,
    name: str,
    code: str,
    base_url: str,
    country: str,
    language: str,
    category: str,
) -> NewsSource:
    src = db.query(NewsSource).filter(NewsSource.code == code).first()
    if src:
        return src
    src = NewsSource(
        name=name,
        code=code,
        base_url=base_url or "https://example.com",
        country=country or "CN",
        language=language or "zh",
        category=category or "news",
        is_active=True,
    )
    db.add(src)
    db.flush()
    return src


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
    if geo_type == "city":
        return "POINT"
    return "POLYGON"


def _get_or_create_geo_entity(db: Session, payload: Dict[str, Any]) -> GeoEntity:
    geo_key = (payload.get("geo_key") or "").strip()[:20]
    geo = db.query(GeoEntity).filter(GeoEntity.geo_key == geo_key).first()
    if geo:
        if not geo.lat and payload.get("lat") is not None:
            geo.lat = payload.get("lat")
        if not geo.lng and payload.get("lng") is not None:
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
        country_name=(payload.get("country_name") or None),
        admin1_code=(payload.get("admin1_code") or None),
        admin1_name=(payload.get("admin1_name") or None),
        city_name=(payload.get("city_name") or None),
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
        m.geo_key: m
        for m in db.query(EventGeoMapping).filter(EventGeoMapping.event_id == event.id).all()
    }

    seen_geo_keys: set[str] = set()
    for idx, geo_payload in enumerate(raw_geo_entities):
        geo_key = (geo_payload.get("geo_key") or "").strip()[:20]
        if not geo_key or geo_key in seen_geo_keys:
            continue
        seen_geo_keys.add(geo_key)

        geo = _get_or_create_geo_entity(db, geo_payload)
        mapping = existing.get(geo_key)
        if mapping is None:
            mapping = EventGeoMapping(
                event_id=event.id,
                geo_id=geo.id,
                geo_key=geo_key,
            )
            db.add(mapping)

        mapping.geo_id = geo.id
        mt = (geo_payload.get("matched_text") or geo_payload.get("name") or geo.name or geo_key)[:500]
        mapping.matched_text = mt
        has_text_scan = bool(geo_payload.get("matched_text")) or bool(geo_payload.get("source_text_position"))
        mapping.extraction_method = "dictionary_match+text_scan" if has_text_scan else "dictionary_match"
        mapping.confidence = float(geo_payload.get("confidence") or 1.0)
        rs = geo_payload.get("relevance_score")
        mapping.relevance_score = float(rs) if rs is not None else (1.0 if idx == 0 else 0.8)
        mapping.is_primary = bool(geo_payload.get("is_primary")) if geo_payload.get("is_primary") is not None else idx == 0
        stp = geo_payload.get("source_text_position")
        mapping.source_text_position = (stp or ("title" if idx == 0 else None))


def ingest_crawled_articles(db: Session, items: List[dict]) -> dict:
    """
    Insert/update news_articles and news_events so /api/news/hot returns data.
    """
    created_articles = 0
    skipped = 0
    events_touched = 0

    for raw in items:
        title = (raw.get("title") or "").strip()
        url = (raw.get("url") or "").strip()
        h = (raw.get("hash") or raw.get("content_hash") or "").strip()
        if not title or not url or not h:
            skipped += 1
            continue

        norm_url = _normalize_url(url)
        dup = (
            db.query(NewsArticle)
            .filter(
                (NewsArticle.hash == h)
                | (NewsArticle.article_url == url)
                | (NewsArticle.article_url == norm_url)
            )
            .first()
        )
        if dup:
            skipped += 1
            continue

        source = get_or_create_source(
            db,
            name=raw.get("source_name") or "Unknown",
            code=raw.get("source_code") or "unknown",
            base_url=raw.get("source_url") or url,
            country=raw.get("country") or "CN",
            language=raw.get("language") or "zh",
            category=raw.get("category") or "news",
        )

        crawl_time = _parse_datetime(raw.get("crawled_at")) or datetime.utcnow()
        pub_time = _parse_datetime(raw.get("published_at"))

        tags = raw.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]

        region_tags = raw.get("region_tags") or []
        if isinstance(region_tags, str):
            region_tags = [region_tags]
        region_tags = [str(x).strip() for x in region_tags if x][:30]

        raw_geo_entities = raw.get("geo_entities") or []
        if not isinstance(raw_geo_entities, list):
            raw_geo_entities = []

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

        article = NewsArticle(
            title=title[:500],
            summary=(raw.get("summary") or None),
            content=(raw.get("content") or None),
            article_url=url[:2000],
            source_id=source.id,
            source_name=source.name,
            source_code=source.code,
            source_url=source.base_url,
            publish_time=pub_time,
            crawl_time=crawl_time,
            heat_score=int(raw.get("heat_score") or 0),
            category=(raw.get("category") or None),
            language=(raw.get("language") or "zh")[:10],
            country_tags=[raw.get("country")] if raw.get("country") else [],
            city_tags=[],
            region_tags=region_tags,
            tags=tags if isinstance(tags, list) else [],
            hash=h[:64],
        )
        db.add(article)
        db.flush()

        title_hash = _normalize_title_hash(title)
        summary = (raw.get("summary") or "")[:2000] if raw.get("summary") else None
        heat = int(raw.get("heat_score") or 0)
        now = datetime.utcnow()

        ev = db.query(NewsEvent).filter(NewsEvent.title_hash == title_hash).first()
        is_new_event = ev is None
        if ev:
            ev.last_seen_at = now
            # Accumulate heat score with mild decay: new = old + new_heat (capped at 9999)
            ev.heat_score = min(9999, (ev.heat_score or 0) + heat)
            ev.article_count = (ev.article_count or 0) + 1
            # Only update main_country if not already set
            if not ev.main_country and main_country:
                ev.main_country = main_country
            if not ev.event_level or ev.event_level == "country":
                ev.event_level = event_level
            if summary and not ev.summary:
                ev.summary = summary
            if not ev.category and raw.get("category"):
                ev.category = raw.get("category")
            events_touched += 1
        else:
            ev = NewsEvent(
                title=title[:500],
                summary=summary,
                main_country=main_country,
                event_level=event_level,
                heat_score=max(heat, 1),
                article_count=1,
                category=(raw.get("category") or None),
                title_hash=title_hash,
                first_seen_at=now,
                last_seen_at=now,
            )
            db.add(ev)
            db.flush()
            events_touched += 1

        link = EventArticle(event_id=ev.id, article_id=article.id, is_primary=is_new_event)
        db.add(link)
        _sync_event_geo_mappings(db, ev, raw_geo_entities)

        created_articles += 1

    db.commit()
    return {
        "created_articles": created_articles,
        "skipped_duplicates": skipped,
        "events_touched": events_touched,
    }
