"""
NASA EONET structured event spider.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime
from typing import Any, Iterator
from urllib.parse import urlencode

from scrapy import Request

from news_crawler.items import NewsArticle
from news_crawler.spiders.base import BaseNewsSpider
from news_crawler.utils.enhanced_geo_processor import EnhancedGeoProcessor
from news_crawler.utils.geo_extractor import GeoExtractor
from news_crawler.utils.geo_text_builder import build_geo_search_text
from news_crawler.utils.source_job_profile import resolve_source_job_profile, update_source_job_checkpoint
from news_crawler.utils.source_profile import resolve_source_profile


class EONETEventsSpider(BaseNewsSpider):
    name = "eonet_events"
    job_name = "eonet_events_realtime"
    job_mode = "realtime"
    source_name = "NASA EONET"
    source_code = "eonet_events"
    source_url = "https://eonet.gsfc.nasa.gov/api/v3/events"
    country = "UNKNOWN"
    language = "en"
    category = "event"
    source_class = "event"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        profile = resolve_source_profile(
            code=self.source_code,
            base_url=self.source_url,
            category=self.category,
            name=self.source_name,
            source_class=self.source_class,
        )
        params = profile.get("default_params_json") or {}
        fallback_job = {
            "source_code": self.source_code,
            "source_class": "event",
            "job_mode": self.job_mode,
            "window_mode": "relative" if self.job_mode == "realtime" else "absolute",
            "cursor_strategy": "last_seen_source_updated_at",
            "enabled": True,
            "schedule_minutes": 30 if self.job_mode == "realtime" else 360,
            "priority": 8 if self.job_mode == "realtime" else 4,
            "default_params_json": params.get(self.job_mode) if isinstance(params, dict) and self.job_mode in params else params,
            "notes": None,
        }
        job_profile = resolve_source_job_profile(self.job_name, fallback_job)
        params = job_profile.get("default_params_json") or {}
        raw_categories = params.get("category") or params.get("categories") or ["wildfires", "severeStorms", "volcanoes"]
        if isinstance(raw_categories, str):
            self.categories = [value.strip() for value in raw_categories.split(",") if value.strip()]
        else:
            self.categories = [str(value).strip() for value in raw_categories if str(value).strip()]
        self.status = str(params.get("status") or "open").strip().lower()
        self.days = int(params.get("days") or 7)
        self.limit = int(params.get("limit") or 200)
        self._geo_extractor = GeoExtractor()
        self._geo_processor = EnhancedGeoProcessor()
        self._job_profile = job_profile
        self._checkpoint = {
            "last_success_at": None,
            "last_seen_external_id": None,
            "last_seen_source_updated_at": None,
            "last_event_time": None,
        }

    def start_requests(self) -> Iterator[Request]:
        query = urlencode(
            {
                "status": self.status,
                "days": self.days,
                "category": ",".join(self.categories),
                "limit": self.limit,
            }
        )
        yield Request(
            url=f"{self.source_url}?{query}",
            callback=self.parse_feed,
            dont_filter=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json, */*",
            },
        )

    def parse_feed(self, response, **kwargs) -> Iterator[NewsArticle]:
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            with urllib.request.urlopen(response.url, timeout=20) as remote:
                payload = json.load(remote)
        events = payload.get("events") or []
        for event in events:
            if len(self.crawled_items) >= self.max_items:
                break
            item = self._build_item(event)
            if item is None:
                continue
            self._track_checkpoint(item)
            self.crawled_items.append(item)
            yield item

    def _build_item(self, event: dict) -> NewsArticle | None:
        external_id = str(event.get("id") or "").strip()
        title = self.clean_text(event.get("title") or "")
        if not external_id or not title:
            return None

        geometry_items = event.get("geometry") or []
        latest_geometry = self._latest_geometry(geometry_items)
        if latest_geometry is None:
            return None

        event_time = latest_geometry.get("date")
        link = (event.get("link") or f"{self.source_url}/{external_id}").strip()
        event_status = "closed" if event.get("closed") else "open"
        lat, lng = self._geometry_center(latest_geometry.get("coordinates"))

        categories = event.get("categories") or []
        tags = [
            str(category.get("id") or category.get("title") or "").strip().lower()
            for category in categories
            if str(category.get("id") or category.get("title") or "").strip()
        ]
        title_hint = ", ".join(str(category.get("title") or "") for category in categories if category.get("title"))
        geo_entities, region_tags = self._derive_geo_entities(
            text_parts=[title, event.get("description") or "", title_hint],
            point_key=f"EONET:{external_id}",
            point_name=title,
            lat=lat,
            lng=lng,
        )

        item = NewsArticle()
        item["title"] = title
        item["summary"] = self.clean_text(event.get("description") or title)
        item["content"] = self.clean_text(event.get("description") or title)
        item["url"] = link
        item["published_at"] = event_time
        item["event_time"] = event_time
        item["event_status"] = event_status
        item["closed_at"] = event.get("closed")
        item["source_updated_at"] = event_time
        item["source_name"] = self.source_name
        item["source_code"] = self.source_code
        item["source_url"] = self.source_url
        item["source_class"] = "event"
        item["crawled_at"] = datetime.now().isoformat()
        item["language"] = self.language
        item["country"] = region_tags[0] if region_tags else self.country
        item["category"] = "disaster"
        item["geo"] = "point"
        item["geom_type"] = str(latest_geometry.get("type") or "Point")
        item["raw_geometry"] = {
            "type": "GeometryCollection",
            "geometries": geometry_items,
        }
        item["display_geo"] = self._display_geo(latest_geometry)
        item["bbox"] = self._bbox_for_geometry_collection(geometry_items)
        item["geo_entities"] = geo_entities
        item["region_tags"] = region_tags
        item["severity"] = self._severity_from_event(categories, latest_geometry)
        item["confidence"] = 88 if event_status == "open" else 84
        item["canonical_url"] = link
        item["external_id"] = external_id
        item["tags"] = sorted(set(tags + ["eonet", "natural_event"]))
        item["heat_score"] = max(item["severity"], 45)
        item["hash"] = self.compute_hash(self.source_code, external_id)
        return item

    def _derive_geo_entities(
        self,
        *,
        text_parts: list[str],
        point_key: str,
        point_name: str,
        lat: float | None,
        lng: float | None,
    ) -> tuple[list[dict], list[str]]:
        title = text_parts[0] if text_parts else ""
        summary = text_parts[1] if len(text_parts) > 1 else ""
        content = " ".join(part for part in text_parts[2:] if part)
        text = build_geo_search_text(title, summary, content)
        region_tags: list[str] = []
        normalized_entities: list[dict] = []
        if text:
            raw_entities = self._geo_extractor.extract(text)
            region_tags = self._geo_extractor.get_country_tags(text)
            normalized_entities = self._geo_processor.normalize_entities(raw_entities)
            normalized_entities = self._geo_processor.merge_entities(
                normalized_entities,
                self._geo_processor.extract_candidates_from_text(text, max_entities=6),
            )

        country_code = ""
        country_name = None
        for entity in normalized_entities:
            code = str(entity.get("country_code") or "").strip().upper()
            if code and code not in region_tags:
                region_tags.append(code)
            if not country_code and code:
                country_code = code
                country_name = entity.get("country_name")

        entities: list[dict] = []
        if lat is not None and lng is not None:
            entities.append(
                {
                    "name": point_name[:100],
                    "geo_key": point_key[:20],
                    "type": "point",
                    "confidence": 0.98,
                    "country_code": country_code or "UNKNOWN",
                    "country_name": country_name,
                    "precision_level": "POINT",
                    "display_mode": "POINT",
                    "geojson_key": point_key[:100],
                    "lat": lat,
                    "lng": lng,
                    "matched_text": point_name[:100],
                    "source_text_position": "title",
                    "relevance_score": 0.98,
                    "is_primary": True,
                }
            )
        for entity in normalized_entities[:4]:
            entity["is_primary"] = not entities
            entities.append(entity)
        return entities, region_tags

    @staticmethod
    def _latest_geometry(geometry_items: list[dict]) -> dict | None:
        if not geometry_items:
            return None
        return max(
            geometry_items,
            key=lambda item: str(item.get("date") or ""),
        )

    def _geometry_center(self, coordinates: Any) -> tuple[float | None, float | None]:
        points: list[tuple[float, float]] = []

        def _walk(value: Any) -> None:
            if not isinstance(value, list):
                return
            if len(value) >= 2 and all(isinstance(coord, (int, float)) for coord in value[:2]):
                points.append((float(value[1]), float(value[0])))
                return
            for item in value:
                _walk(item)

        _walk(coordinates)
        if not points:
            return None, None
        lat = sum(point[0] for point in points) / len(points)
        lng = sum(point[1] for point in points) / len(points)
        return lat, lng

    def _bbox_for_geometry_collection(self, geometry_items: list[dict]) -> list[float] | None:
        points: list[tuple[float, float]] = []
        for geometry in geometry_items:
            lat, lng = self._geometry_center(geometry.get("coordinates"))
            if lat is None or lng is None:
                continue
            points.append((lat, lng))
        if not points:
            return None
        lats = [point[0] for point in points]
        lngs = [point[1] for point in points]
        return [min(lngs), min(lats), max(lngs), max(lats)]

    def _display_geo(self, geometry: dict) -> dict | None:
        lat, lng = self._geometry_center(geometry.get("coordinates"))
        if lat is None or lng is None:
            return None
        return {"type": "Point", "coordinates": [lng, lat]}

    @staticmethod
    def _severity_from_event(categories: list[dict], geometry: dict) -> int:
        category_ids = {str(category.get("id") or "").strip().lower() for category in categories}
        if "volcanoes" in category_ids:
            base = 84
        elif "severestorms" in category_ids:
            base = 76
        elif "wildfires" in category_ids:
            base = 72
        else:
            base = 65

        magnitude = geometry.get("magnitudeValue")
        try:
            if magnitude is not None:
                base += min(12, int(round(float(magnitude))))
        except (TypeError, ValueError):
            pass
        return max(40, min(95, base))

    def _track_checkpoint(self, item: NewsArticle) -> None:
        self._checkpoint["last_success_at"] = datetime.now().isoformat()
        self._checkpoint["last_seen_external_id"] = item.get("external_id")
        self._checkpoint["last_seen_source_updated_at"] = self._iso_string(item.get("source_updated_at"))
        self._checkpoint["last_event_time"] = self._iso_string(item.get("event_time"))

    def closed(self, reason: str):
        if self._checkpoint["last_success_at"]:
            update_source_job_checkpoint(
                job_name=self.job_name,
                source_code=self.source_code,
                job_mode=self.job_mode,
                last_success_at=self._checkpoint["last_success_at"],
                last_seen_external_id=self._checkpoint["last_seen_external_id"],
                last_seen_source_updated_at=self._checkpoint["last_seen_source_updated_at"],
                last_event_time=self._checkpoint["last_event_time"],
            )
        super().closed(reason)

    @staticmethod
    def _iso_string(value) -> str | None:
        if isinstance(value, str):
            return value
        return None
