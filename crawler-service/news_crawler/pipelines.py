"""
Scrapy Pipelines for processing crawled news items.

This module contains the data processing pipelines that clean,
validate, and store crawled news data.
"""
import hashlib
import json
import logging
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, Optional

from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem

from news_crawler.direct_ingest import try_direct_ingest
from news_crawler.utils.feed_control import (
    record_feed_direct_result,
    record_feed_fresh_item,
    record_feed_quality_drop,
    record_feed_scraped,
    record_feed_stale_drop,
)
from news_crawler.utils.news_signal import classify_news_signal
from news_crawler.utils.source_profile import resolve_source_profile

logger = logging.getLogger(__name__)


def _normalize_timestamp(value: Any, spider) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value
    if isinstance(value, (int, float)):
        try:
            numeric = float(value)
            if numeric > 10_000_000_000:
                numeric /= 1000.0
            return datetime.fromtimestamp(numeric, tz=timezone.utc).replace(tzinfo=None)
        except (OverflowError, OSError, ValueError):
            return None

    parser = getattr(spider, "parse_datetime", None)
    if callable(parser):
        try:
            parsed = parser(value)
            if parsed is not None:
                return parsed
        except Exception:
            logger.debug("[Time] spider.parse_datetime failed for value=%r", value, exc_info=True)
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            dt = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
            return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt
        except ValueError:
            pass
        try:
            dt = parsedate_to_datetime(cleaned)
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        except Exception:
            return None
    return None


def _normalize_percent(value: Any, *, default: int = 100) -> int:
    if value is None:
        return default
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if numeric <= 1:
        numeric *= 100
    return max(0, min(100, int(round(numeric))))


class NewsCrawlerPipeline:
    """
    Main pipeline for processing news articles.
    Cleans text, normalizes data, and prepares items for storage.
    """
    
    def __init__(self):
        self.crawled_count = 0
        self.dropped_count = 0
    
    def process_item(self, item, spider):
        """Process a crawled item."""
        adapter = ItemAdapter(item)
        
        # Clean and normalize text fields
        if title := adapter.get("title"):
            adapter["title"] = self._clean_text(title)
        
        if summary := adapter.get("summary"):
            adapter["summary"] = self._clean_text(summary)
        
        if content := adapter.get("content"):
            adapter["content"] = self._clean_text(content)
        
        # Set crawled timestamp if not present
        if not adapter.get("crawled_at"):
            adapter["crawled_at"] = datetime.utcnow().isoformat()
        
        # Normalize source name
        if source_name := adapter.get("source_name"):
            adapter["source_name"] = self._normalize_source(source_name)
        
        # Calculate hash for deduplication
        url = adapter.get("url", "")
        title = adapter.get("title", "")
        if url and title:
            content = f"{url}|{title}"
            adapter["hash"] = hashlib.sha256(content.encode()).hexdigest()
        
        # Calculate basic heat score (can be enhanced)
        heat_score = adapter.get("heat_score", 0)
        if heat_score == 0:
            content_length = len(adapter.get("content", "") or "")
            adapter["heat_score"] = min(100, content_length // 100)
        
        self.crawled_count += 1
        record_feed_scraped(spider, adapter)
        title_preview = (adapter.get("title") or "No title")[:50]
        logger.info(f"[Pipeline] Processed item: {title_preview}")
        
        return item
    
    def _clean_text(self, text: Optional[str]) -> Optional[str]:
        """Clean text by removing extra whitespace and HTML."""
        if not text:
            return None
        
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip() or None
    
    def _normalize_source(self, source: str) -> str:
        """Normalize source name to standard display format."""
        source_map = {
            # Chinese sources
            "新浪": "新浪新闻",
            "新浪网": "新浪新闻",
            "腾讯": "腾讯新闻",
            "腾讯网": "腾讯新闻",
            "微博": "微博热搜",
            "知乎": "知乎热榜",
            # International — variants to canonical
            "BBC": "BBC News",
            "bbc": "BBC News",
            "AP": "AP News",
            "Associated Press": "AP News",
            "Guardian": "The Guardian",
            "guardian": "The Guardian",
            "The Guardian": "The Guardian",
            "Al Jazeera": "Al Jazeera",
            "aljazeera": "Al Jazeera",
            "DW": "Deutsche Welle",
            "Deutsche Welle": "Deutsche Welle",
            "France 24": "France 24",
            "france24": "France 24",
            "CNA": "Channel NewsAsia",
            "Channel NewsAsia": "Channel NewsAsia",
            "SCMP": "South China Morning Post",
            "South China Morning Post": "South China Morning Post",
            "NHK": "NHK World",
            "NHK World": "NHK World",
            "NDTV": "NDTV",
            "CNN": "CNN",
            "Reuters": "Reuters",
            "reuters": "Reuters",
            "Global Times": "Global Times",
            # Social / other
            "Twitter": "Twitter",
            "推特": "Twitter",
        }
        return source_map.get(source, source)
    
    def open_spider(self, spider):
        """Called when spider is opened."""
        self.crawled_count = 0
        self.dropped_count = 0
        logger.info(f"[Pipeline] Spider {spider.name} opened")
    
    def close_spider(self, spider):
        """Called when spider is closed."""
        logger.info(f"[Pipeline] Spider {spider.name} closed. "
                   f"Processed: {self.crawled_count}, Dropped: {self.dropped_count}")


class DeduplicationPipeline:
    """
    Pipeline for detecting and filtering duplicate items.
    Uses hash-based deduplication.
    """
    
    def __init__(self):
        self.seen_hashes = set()
    
    def process_item(self, item, spider):
        """Check for duplicates and filter them."""
        adapter = ItemAdapter(item)

        item_hash = adapter.get("hash")
        source_class = (adapter.get("source_class") or "news").strip().lower()
        if source_class == "event":
            external_id = str(adapter.get("external_id") or "").strip()
            canonical_url = str(adapter.get("canonical_url") or adapter.get("url") or "").strip()
            event_time = str(adapter.get("event_time") or adapter.get("published_at") or "").strip()
            event_key = external_id or f"{canonical_url}|{event_time}|{adapter.get('title') or ''}"
            if event_key:
                item_hash = hashlib.sha256(event_key.encode("utf-8")).hexdigest()
                adapter["hash"] = item_hash

        if not item_hash:
            url = adapter.get("url", "")
            title = adapter.get("title", "")
            if url and title:
                content = f"{url}|{title}"
                item_hash = hashlib.sha256(content.encode()).hexdigest()
                adapter["hash"] = item_hash
        
        if item_hash and item_hash in self.seen_hashes:
            logger.debug(f"[Dedup] Duplicate item filtered: {item_hash}")
            raise DropItem(f"Duplicate item found: {item_hash}")
        
        if item_hash:
            self.seen_hashes.add(item_hash)
        
        return item
    
    def open_spider(self, spider):
        """Called when spider is opened."""
        self.seen_hashes.clear()
        logger.info(f"[Dedup] Pipeline opened for {spider.name}")


class SourceProfilePipeline:
    """Attach source-class metadata so downstream pipes can branch by source type."""

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        profile = resolve_source_profile(
            code=adapter.get("source_code") or spider.name,
            base_url=adapter.get("source_url") or adapter.get("url") or "",
            category=adapter.get("category") or "news",
            name=adapter.get("source_name") or spider.name,
            source_class=adapter.get("source_class"),
            freshness_sla_hours=adapter.get("freshness_sla_hours"),
            license_mode=adapter.get("license_mode"),
        )
        if not profile.get("enabled", True):
            raise DropItem(f"Source disabled by policy: {adapter.get('source_code') or spider.name}")
        for key, value in profile.items():
            if adapter.get(key) in (None, "", []):
                adapter[key] = value

        if not adapter.get("canonical_url"):
            adapter["canonical_url"] = adapter.get("url")
        if adapter.get("confidence") in (None, ""):
            adapter["confidence"] = 1.0
        if adapter.get("severity") in (None, ""):
            adapter["severity"] = 0
        if adapter.get("geom_type") in (None, "") and adapter.get("display_geo"):
            geometry = adapter.get("display_geo") or {}
            adapter["geom_type"] = geometry.get("type")
        return item


class EventSchemaPipeline:
    """Validate and normalize structured event feeds before dedup/timeliness."""

    def __init__(self):
        self.filtered_invalid = 0

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        source_class = (adapter.get("source_class") or "news").strip().lower()
        if source_class != "event":
            return item

        event_dt = _normalize_timestamp(adapter.get("event_time"), spider)
        publish_dt = _normalize_timestamp(adapter.get("published_at"), spider)
        closed_dt = _normalize_timestamp(adapter.get("closed_at"), spider)
        source_updated_dt = _normalize_timestamp(adapter.get("source_updated_at"), spider)
        signal_dt = event_dt or publish_dt
        if signal_dt is None:
            self.filtered_invalid += 1
            raise DropItem(f"Invalid event item: missing event_time/published_at title={adapter.get('title')!r}")

        adapter["event_time"] = signal_dt.isoformat()
        if publish_dt is not None:
            adapter["published_at"] = publish_dt.isoformat()
        if closed_dt is not None:
            adapter["closed_at"] = closed_dt.isoformat()
        if source_updated_dt is not None:
            adapter["source_updated_at"] = source_updated_dt.isoformat()

        external_id = str(adapter.get("external_id") or "").strip()
        canonical_url = str(adapter.get("canonical_url") or adapter.get("url") or "").strip()
        if not external_id and not canonical_url:
            self.filtered_invalid += 1
            raise DropItem(f"Invalid event item: missing external_id/canonical_url title={adapter.get('title')!r}")

        event_status = str(adapter.get("event_status") or "").strip().lower()
        if event_status not in {"open", "closed", "active"}:
            event_status = "closed"
        adapter["event_status"] = "open" if event_status == "active" else event_status
        adapter["confidence"] = _normalize_percent(adapter.get("confidence"), default=85)
        adapter["severity"] = _normalize_percent(adapter.get("severity"), default=25)
        if not adapter.get("hash"):
            dedup_basis = external_id or f"{canonical_url}|{signal_dt.isoformat()}|{adapter.get('title') or ''}"
            adapter["hash"] = hashlib.sha256(dedup_basis.encode("utf-8")).hexdigest()
        return item

    def open_spider(self, spider):
        self.filtered_invalid = 0

    def close_spider(self, spider):
        logger.info("[EventSchema] %s invalid_filtered=%s", spider.name, self.filtered_invalid)


class IntakeQualityPipeline:
    """News/lead quality lane: semantic tags, coarse category normalization, low-value filter."""

    def __init__(self, *, filter_low_value: bool = True):
        self.filter_low_value = bool(filter_low_value)
        self.filtered_low_value = 0

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            filter_low_value=bool(crawler.settings.getbool("NEWS_FILTER_LOW_VALUE", True)),
        )

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        source_class = (adapter.get("source_class") or "news").strip().lower()
        if source_class == "event":
            return item

        signal = classify_news_signal(
            title=adapter.get("title"),
            summary=adapter.get("summary"),
            content=adapter.get("content"),
            source_code=adapter.get("source_code"),
            base_category=adapter.get("category"),
        )

        if signal.tags:
            adapter["tags"] = self._merge_tags(adapter.get("tags"), signal.tags)

        if signal.category:
            adapter["category"] = signal.category

        adapter["confidence"] = _normalize_percent(adapter.get("confidence"), default=100)
        adapter["severity"] = _normalize_percent(adapter.get("severity"), default=0)

        if self.filter_low_value and signal.should_drop:
            self.filtered_low_value += 1
            record_feed_quality_drop(spider, adapter)
            raise DropItem(
                f"Low-value item filtered: negatives={signal.matched_negative[:4]} title={adapter.get('title')!r}"
            )

        return item

    def open_spider(self, spider):
        self.filtered_low_value = 0
        logger.info(
            "[Quality] Pipeline opened for %s (filter_low_value=%s)",
            spider.name,
            self.filter_low_value,
        )

    def close_spider(self, spider):
        logger.info("[Quality] Pipeline closed for %s. low_value_filtered=%s", spider.name, self.filtered_low_value)

    @staticmethod
    def _merge_tags(existing: Any, derived: list[str]) -> list[str]:
        ordered: list[str] = []
        if isinstance(existing, str):
            existing_iter = [part.strip() for part in existing.split(",") if part.strip()]
        else:
            existing_iter = existing or []
        for value in existing_iter:
            if value and value not in ordered:
                ordered.append(value)
        for value in derived:
            if value and value not in ordered:
                ordered.append(value)
        return ordered


class TimelinessPipeline:
    """Apply freshness SLAs after source-class routing and quality normalization."""

    def __init__(self, *, default_max_age_hours: int = 24, allow_missing_published_at: bool = True):
        self.default_max_age_hours = max(1, int(default_max_age_hours))
        self.allow_missing_published_at = bool(allow_missing_published_at)
        self.filtered_stale = 0

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            default_max_age_hours=int(crawler.settings.get("NEWS_MAX_AGE_HOURS", 24)),
            allow_missing_published_at=bool(crawler.settings.getbool("NEWS_ALLOW_MISSING_PUBLISHED_AT", True)),
        )

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        source_class = (adapter.get("source_class") or "news").strip().lower()
        freshness_sla_hours = int(adapter.get("freshness_sla_hours") or self.default_max_age_hours)
        time_field = "event_time" if source_class == "event" else "published_at"
        signal_dt = _normalize_timestamp(adapter.get(time_field), spider)
        if signal_dt is None and time_field != "published_at":
            signal_dt = _normalize_timestamp(adapter.get("published_at"), spider)
        if signal_dt is None:
            if self.allow_missing_published_at and source_class != "event":
                record_feed_fresh_item(spider, adapter)
                return item
            self.filtered_stale += 1
            record_feed_stale_drop(spider, adapter)
            raise DropItem(f"Missing signal time filtered: field={time_field} title={adapter.get('title')!r}")

        adapter[time_field] = signal_dt.isoformat()
        if source_class == "event":
            event_status = str(adapter.get("event_status") or "closed").strip().lower()
            if event_status == "open":
                return item
            closed_dt = _normalize_timestamp(adapter.get("closed_at"), spider)
            updated_dt = _normalize_timestamp(adapter.get("source_updated_at"), spider)
            lifecycle_dt = closed_dt or updated_dt or signal_dt
            if closed_dt is not None:
                adapter["closed_at"] = closed_dt.isoformat()
            if updated_dt is not None:
                adapter["source_updated_at"] = updated_dt.isoformat()
            age_hours = (datetime.now(timezone.utc).replace(tzinfo=None) - lifecycle_dt).total_seconds() / 3600.0
            if age_hours > freshness_sla_hours:
                self.filtered_stale += 1
                record_feed_stale_drop(spider, adapter)
                raise DropItem(
                    f"Stale event filtered: age_hours={age_hours:.1f} > {freshness_sla_hours} title={adapter.get('title')!r}"
                )
            record_feed_fresh_item(spider, adapter)
            return item

        age_hours = (datetime.now(timezone.utc).replace(tzinfo=None) - signal_dt).total_seconds() / 3600.0
        if age_hours > freshness_sla_hours:
            self.filtered_stale += 1
            record_feed_stale_drop(spider, adapter)
            raise DropItem(
                f"Stale item filtered: age_hours={age_hours:.1f} > {freshness_sla_hours} title={adapter.get('title')!r}"
            )
        record_feed_fresh_item(spider, adapter)
        return item

    def open_spider(self, spider):
        self.filtered_stale = 0
        logger.info(
            "[Timeliness] Pipeline opened for %s (default_max_age_hours=%s, allow_missing_published_at=%s)",
            spider.name,
            self.default_max_age_hours,
            self.allow_missing_published_at,
        )

    def close_spider(self, spider):
        logger.info("[Timeliness] Pipeline closed for %s. stale_filtered=%s", spider.name, self.filtered_stale)


class GeoExtractionPipeline:
    """
    Pipeline for extracting geographic entities from title + first paragraph only.
    Fills ``region_tags`` (ISO-like codes) for DB / globe filtering.
    """

    def __init__(self):
        self._geo = None
        self._processor = None

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        if (adapter.get("source_class") or "news").strip().lower() == "event":
            return item
        title = (adapter.get("title") or "").strip()
        summary = adapter.get("summary") or ""
        content = adapter.get("content") or ""
        try:
            from news_crawler.utils.enhanced_geo_processor import EnhancedGeoProcessor
            from news_crawler.utils.location_matcher import LocationMatcher
            from news_crawler.utils.geo_extractor import GeoExtractor
            from news_crawler.utils.geo_text_builder import build_geo_search_text

            if self._geo is None:
                self._geo = GeoExtractor()
            if self._processor is None:
                self._processor = EnhancedGeoProcessor()
            if not hasattr(self, "_matcher") or self._matcher is None:
                self._matcher = LocationMatcher()

            text = build_geo_search_text(title, summary, content)
            if not text:
                return item

            geo_entities = self._geo.extract(text)
            region_tags = self._geo.get_country_tags(text)

            normalized_geo_entities = self._processor.normalize_entities(geo_entities)
            country_hints = self._collect_country_hints(normalized_geo_entities, region_tags)
            admin1_hints_by_country = self._collect_admin1_hints(normalized_geo_entities)

            text_geo_groups = []
            if country_hints:
                for country_hint in country_hints[:3]:
                    text_geo_groups.append(
                        self._processor.extract_candidates_from_text(
                            text,
                            country_hint=country_hint,
                            admin1_hints=admin1_hints_by_country.get(country_hint) or None,
                            max_entities=14,
                        )
                    )
            text_geo_groups.append(self._processor.extract_candidates_from_text(text, max_entities=12))
            normalized_geo_entities = self._processor.merge_entities(normalized_geo_entities, *text_geo_groups)

            refined_admin1_hints = self._collect_admin1_hints(normalized_geo_entities)
            refined_groups = []
            for country_hint in country_hints[:3]:
                admin1_hints = refined_admin1_hints.get(country_hint) or admin1_hints_by_country.get(country_hint) or []
                if not admin1_hints:
                    continue
                refined_groups.append(
                    self._processor.extract_candidates_from_text(
                        text,
                        country_hint=country_hint,
                        admin1_hints=admin1_hints,
                        max_entities=14,
                    )
                )
            if refined_groups:
                normalized_geo_entities = self._processor.merge_entities(normalized_geo_entities, *refined_groups)
            # annotate matched_text and source_text_position
            normalized_geo_entities = self._matcher.annotate_matches(
                title=title,
                summary=summary,
                content=content,
                entities=normalized_geo_entities,
            )
            normalized_geo_entities = self._sort_geo_entities(normalized_geo_entities)
            normalized_geo_entities = self._dedupe_ambiguous_entities(normalized_geo_entities)

            if normalized_geo_entities:
                derived_region_tags = []
                for entity in normalized_geo_entities:
                    cc = (entity.get("country_code") or "").strip().upper()
                    if cc and cc not in derived_region_tags:
                        derived_region_tags.append(cc)
                adapter["geo_entities"] = normalized_geo_entities
                adapter["geo_locations"] = [
                    {"name": e.get("name"), "lat": e.get("lat"), "lng": e.get("lng")}
                    for e in normalized_geo_entities
                ]
                if derived_region_tags:
                    region_tags = derived_region_tags
            if region_tags:
                adapter["region_tags"] = region_tags
        except Exception as e:
            logger.warning("[Geo] Failed: %s", e)

        return item

    @staticmethod
    def _sort_geo_entities(entities: list[dict]) -> list[dict]:
        if not entities:
            return []

        type_weight = {"province": 1.0, "admin1": 1.0, "city": 0.92, "country": 0.86}
        pos_weight = {"title": 1.0, "summary": 0.8, "content": 0.6}
        granularity_bonus = {"province": 0.06, "admin1": 0.06, "city": 0.04, "country": 0.0}
        sorted_entities = sorted(
            entities,
            key=lambda e: (
                float(e.get("relevance_score") or 0.0) + granularity_bonus.get((e.get("type") or "").lower(), 0.0),
                type_weight.get((e.get("type") or "").lower(), 0.8),
                pos_weight.get((e.get("source_text_position") or "").lower(), 0.5),
                float(e.get("confidence") or 0.0),
            ),
            reverse=True,
        )
        for idx, entity in enumerate(sorted_entities):
            entity["is_primary"] = idx == 0
        return sorted_entities

    @staticmethod
    def _dedupe_ambiguous_entities(entities: list[dict]) -> list[dict]:
        deduped: list[dict] = []
        seen_keys: set[tuple[str, str, str]] = set()
        for entity in entities:
            geo_type = (entity.get("type") or "").lower()
            country_code = (entity.get("country_code") or "").strip().upper()
            if geo_type == "city":
                label = (entity.get("city_name") or entity.get("name") or "").strip().lower()
            elif geo_type in {"province", "admin1"}:
                label = (entity.get("admin1_name") or entity.get("name") or "").strip().lower()
            elif geo_type == "country":
                label = country_code or (entity.get("country_name") or entity.get("name") or "").strip().lower()
            else:
                label = (entity.get("name") or "").strip().lower()

            key = (geo_type, country_code, label)
            if label and key in seen_keys:
                continue
            seen_keys.add(key)
            deduped.append(entity)

        for idx, entity in enumerate(deduped):
            entity["is_primary"] = idx == 0
        return deduped

    @staticmethod
    def _collect_country_hints(entities: list[dict], region_tags: list[str]) -> list[str]:
        ordered: list[str] = []
        for entity in entities or []:
            cc = (entity.get("country_code") or "").strip().upper()
            if cc and cc not in ordered:
                ordered.append(cc)
        for tag in region_tags or []:
            cc = str(tag or "").strip().upper()
            if cc and cc not in ordered:
                ordered.append(cc)
        return ordered

    @staticmethod
    def _collect_admin1_hints(entities: list[dict]) -> dict[str, list[str]]:
        hints: dict[str, list[str]] = {}
        for entity in entities or []:
            cc = (entity.get("country_code") or "").strip().upper()
            if not cc:
                continue
            values = []
            admin1_code = (entity.get("admin1_code") or "").strip().upper()
            admin1_name = (entity.get("admin1_name") or "").strip()
            if admin1_code:
                values.append(admin1_code)
            if admin1_name:
                values.append(admin1_name)
            if not values:
                continue
            bucket = hints.setdefault(cc, [])
            for value in values:
                if value not in bucket:
                    bucket.append(value)
        return hints


class ApiIngestPipeline:
    """
    POST each item to FastAPI /api/news/ingest so NewsEvent rows exist for the web UI.
    """

    def __init__(self, api_base: str, timeout: int = 30):
        self.ingest_url = api_base.rstrip("/") + "/api/news/ingest"
        self.timeout = timeout

    @classmethod
    def from_crawler(cls, crawler):
        base = crawler.settings.get("API_BASE_URL") or "http://127.0.0.1:8000"
        return cls(api_base=str(base))

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        rt = adapter.get("region_tags") or []
        geo_entities = adapter.get("geo_entities") or []
        if isinstance(rt, str):
            rt = [rt]
        payload: Dict[str, Any] = {
            "title": (adapter.get("title") or "").strip(),
            "summary": adapter.get("summary"),
            "content": adapter.get("content"),
            "url": (adapter.get("url") or "").strip(),
            "source_name": adapter.get("source_name") or "",
            "source_code": adapter.get("source_code") or "",
            "source_url": adapter.get("source_url"),
            "source_class": adapter.get("source_class") or "news",
            "source_tier": adapter.get("source_tier"),
            "source_tier_level": adapter.get("source_tier_level"),
            "language": adapter.get("language") or "zh",
            "country": adapter.get("country") or "CN",
            "category": adapter.get("category"),
            "freshness_sla_hours": adapter.get("freshness_sla_hours"),
            "heat_score": int(adapter.get("heat_score") or 0),
            "severity": adapter.get("severity"),
            "confidence": adapter.get("confidence"),
            "geo": adapter.get("geo"),
            "geom_type": adapter.get("geom_type"),
            "raw_geometry": adapter.get("raw_geometry"),
            "display_geo": adapter.get("display_geo"),
            "bbox": adapter.get("bbox"),
            "source_metadata": adapter.get("source_metadata"),
            "license_mode": adapter.get("license_mode"),
            "canonical_url": adapter.get("canonical_url") or adapter.get("url"),
            "external_id": adapter.get("external_id"),
            "hash": adapter.get("hash") or "",
            "published_at": _json_safe_scalar(adapter.get("published_at")),
            "event_time": _json_safe_scalar(adapter.get("event_time")),
            "event_status": adapter.get("event_status"),
            "closed_at": _json_safe_scalar(adapter.get("closed_at")),
            "source_updated_at": _json_safe_scalar(adapter.get("source_updated_at")),
            "crawled_at": _json_safe_scalar(adapter.get("crawled_at")),
            "tags": adapter.get("tags") or [],
            "region_tags": list(rt) if isinstance(rt, (list, tuple)) else [],
            "geo_entities": geo_entities if isinstance(geo_entities, list) else [],
        }

        if not payload["title"] or not payload["url"] or not payload["hash"]:
            logger.warning("[Ingest] Skip item: missing title/url/hash")
            return item

        if try_direct_ingest(payload):
            record_feed_direct_result(spider, adapter, direct_ok=True)
            logger.info("[Ingest] Direct OK — %s", payload["title"][:60])
            return item
        record_feed_direct_result(spider, adapter, direct_ok=False)

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            self.ingest_url,
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                logger.info("[Ingest] HTTP OK %s — %s", resp.status, raw[:200])
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace") if e.fp else ""
            logger.error("[Ingest] HTTP %s: %s", e.code, err_body[:500])
        except urllib.error.URLError as e:
            logger.error("[Ingest] URL error (is API running?): %s", e.reason)
        except Exception as e:
            logger.exception("[Ingest] Failed: %s", e)

        return item


def _json_safe_scalar(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.isoformat()
    return val
