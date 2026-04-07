"""
USGS realtime earthquake feed spider.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime
from typing import Iterator

from scrapy import Request

from news_crawler.items import NewsArticle
from news_crawler.spiders.base import BaseNewsSpider
from news_crawler.utils.enhanced_geo_processor import EnhancedGeoProcessor
from news_crawler.utils.geo_extractor import GeoExtractor
from news_crawler.utils.geo_text_builder import build_geo_search_text
from news_crawler.utils.source_job_profile import resolve_source_job_profile, update_source_job_checkpoint
from news_crawler.utils.source_profile import resolve_source_profile


class USGSEarthquakeSpider(BaseNewsSpider):
    name = "earthquake_usgs"
    job_name = "earthquake_usgs_realtime"
    job_mode = "realtime"
    source_name = "USGS Earthquake Hazards"
    source_code = "earthquake_usgs"
    source_url = "https://earthquake.usgs.gov/earthquakes/feed/"
    country = "UNKNOWN"
    language = "en"
    category = "event"
    source_class = "event"

    FEED_URLS = {
        "significant_hour": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_hour.geojson",
        "all_hour": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson",
        "significant_day": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_day.geojson",
        "all_day": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson",
    }
    US_STATE_ABBR = {
        "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
        "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
        "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
        "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
        "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri",
        "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
        "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
        "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
        "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
        "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
        "DC": "District of Columbia",
    }

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
            "window_mode": "relative",
            "cursor_strategy": "last_seen_source_updated_at",
            "enabled": True,
            "schedule_minutes": 5 if self.job_mode == "realtime" else 180,
            "priority": 9 if self.job_mode == "realtime" else 5,
            "default_params_json": params.get(self.job_mode) if isinstance(params, dict) and self.job_mode in params else params,
            "notes": None,
        }
        job_profile = resolve_source_job_profile(self.job_name, fallback_job)
        params = job_profile.get("default_params_json") or {}
        configured_feeds = params.get("feeds") or ["significant_hour", "all_hour", "significant_day", "all_day"]
        self.feed_names = [feed for feed in configured_feeds if feed in self.FEED_URLS] or ["all_day"]
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
        for feed_name in self.feed_names:
            yield Request(
                url=self.FEED_URLS[feed_name],
                callback=self.parse_feed,
                dont_filter=True,
                meta={"feed_name": feed_name},
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/geo+json, application/json, */*",
                },
            )

    def parse_feed(self, response, **kwargs) -> Iterator[NewsArticle]:
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            with urllib.request.urlopen(response.url, timeout=20) as remote:
                payload = json.load(remote)
        features = payload.get("features") or []
        for feature in features:
            if len(self.crawled_items) >= self.max_items:
                break
            item = self._build_item(feature)
            if item is None:
                continue
            self._track_checkpoint(item)
            self.crawled_items.append(item)
            yield item

    def _build_item(self, feature: dict) -> NewsArticle | None:
        properties = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates") or []
        if len(coordinates) < 2:
            return None

        external_id = str(feature.get("id") or "").strip()
        title = self.clean_text(properties.get("title") or "")
        if not external_id or not title:
            return None

        url = (properties.get("url") or properties.get("detail") or "").strip()
        if not url:
            return None

        place = self.clean_text(properties.get("place") or "")
        magnitude = properties.get("mag")
        lat = coordinates[1]
        lng = coordinates[0]
        us_state = self._us_state_from_place(place)
        geo_entities, region_tags = self._derive_geo_entities(
            text_parts=[title, place],
            point_key=f"USGS:{external_id}",
            point_name=place or title,
            lat=lat,
            lng=lng,
            us_state=us_state,
        )

        item = NewsArticle()
        item["title"] = title
        item["summary"] = place or title
        item["content"] = place or title
        item["url"] = url
        item["published_at"] = properties.get("time")
        item["event_time"] = properties.get("time")
        item["event_status"] = "closed"
        item["closed_at"] = properties.get("time")
        item["source_updated_at"] = properties.get("updated")
        item["source_name"] = self.source_name
        item["source_code"] = self.source_code
        item["source_url"] = self.source_url
        item["source_class"] = "event"
        item["crawled_at"] = datetime.now().isoformat()
        item["language"] = self.language
        item["country"] = region_tags[0] if region_tags else self.country
        item["category"] = "disaster"
        item["geo"] = "point"
        item["geom_type"] = geometry.get("type") or "Point"
        item["raw_geometry"] = geometry
        item["display_geo"] = {"type": "Point", "coordinates": [lng, lat]}
        item["bbox"] = [lng, lat, lng, lat]
        item["geo_entities"] = geo_entities
        item["region_tags"] = region_tags
        item["severity"] = self._severity_from_properties(properties)
        item["confidence"] = 95
        item["canonical_url"] = url
        item["external_id"] = external_id
        item["tags"] = ["earthquake", "disaster", "seismic"]
        item["heat_score"] = max(item["severity"], 40)
        item["hash"] = self.compute_hash(self.source_code, external_id)
        return item

    def _derive_geo_entities(
        self,
        *,
        text_parts: list[str],
        point_key: str,
        point_name: str,
        lat: float,
        lng: float,
        us_state: dict | None = None,
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
        country_code = "US" if us_state else ""
        country_name = "United States" if us_state else None
        for entity in normalized_entities:
            code = str(entity.get("country_code") or "").strip().upper()
            if us_state and code == "CA":
                continue
            if code and code not in region_tags:
                region_tags.append(code)
            if not country_code and code:
                country_code = code
                country_name = entity.get("country_name")
        if us_state and "US" not in region_tags:
            region_tags.insert(0, "US")
        point_entity = {
            "name": point_name[:100],
            "geo_key": point_key[:20],
            "type": "point",
            "confidence": 0.99,
            "country_code": country_code or "UNKNOWN",
            "country_name": country_name,
            "precision_level": "POINT",
            "display_mode": "POINT",
            "geojson_key": point_key[:100],
            "lat": lat,
            "lng": lng,
            "matched_text": point_name[:100],
            "source_text_position": "title",
            "relevance_score": 0.99,
            "is_primary": True,
        }
        entities = [point_entity]
        if us_state:
            entities.append(
                {
                    "name": us_state["name"],
                    "geo_key": f"US.{us_state['code']}",
                    "type": "province",
                    "confidence": 0.96,
                    "country_code": "US",
                    "country_name": "United States",
                    "admin1_code": us_state["code"],
                    "admin1_name": us_state["name"],
                    "precision_level": "ADMIN1",
                    "display_mode": "POLYGON",
                    "geojson_key": f"US.{us_state['code']}",
                    "lat": lat,
                    "lng": lng,
                    "matched_text": us_state["matched_text"],
                    "source_text_position": "title",
                    "relevance_score": 0.96,
                    "is_primary": False,
                }
            )
        for entity in normalized_entities[:4]:
            if us_state and str(entity.get("country_code") or "").strip().upper() == "CA":
                continue
            entity["is_primary"] = False
            entities.append(entity)
        return entities, region_tags

    @staticmethod
    def _severity_from_properties(properties: dict) -> int:
        alert = str(properties.get("alert") or "").strip().lower()
        if alert == "red":
            return 95
        if alert == "orange":
            return 85
        if alert == "yellow":
            return 72
        if alert == "green":
            return 58

        sig = properties.get("sig")
        try:
            if sig is not None:
                return max(35, min(92, int(round(float(sig) / 10.0))))
        except (TypeError, ValueError):
            pass

        mag = properties.get("mag")
        try:
            if mag is not None:
                return max(30, min(90, int(round(float(mag) * 12))))
        except (TypeError, ValueError):
            pass
        return 40

    @classmethod
    def _us_state_from_place(cls, place: str | None) -> dict | None:
        text = str(place or "").strip()
        if "," not in text:
            return None
        suffix = text.rsplit(",", 1)[-1].strip().upper()
        state_name = cls.US_STATE_ABBR.get(suffix)
        if not state_name:
            return None
        return {
            "code": suffix,
            "name": state_name,
            "matched_text": text.rsplit(",", 1)[-1].strip(),
        }

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

    def _iso_string(self, value) -> str | None:
        dt = None
        if isinstance(value, (int, float)):
            numeric = float(value)
            if numeric > 10_000_000_000:
                numeric /= 1000.0
            dt = datetime.fromtimestamp(numeric)
        elif isinstance(value, str):
            return value
        return dt.isoformat() if dt is not None else None
