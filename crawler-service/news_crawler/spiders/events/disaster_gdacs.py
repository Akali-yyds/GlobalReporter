"""GDACS alert/enrichment event spider."""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator, Optional
from urllib.parse import urlencode

from scrapy import Request

from news_crawler.items import NewsArticle
from news_crawler.spiders.base import BaseNewsSpider
from news_crawler.utils.enhanced_geo_processor import EnhancedGeoProcessor
from news_crawler.utils.geo_extractor import GeoExtractor
from news_crawler.utils.geo_text_builder import build_geo_search_text
from news_crawler.utils.source_job_profile import (
    resolve_source_job_checkpoint,
    resolve_source_job_profile,
    update_source_job_checkpoint,
)
from news_crawler.utils.source_profile import resolve_source_profile


class GDACSDisasterSpider(BaseNewsSpider):
    name = "disaster_gdacs"
    job_name = "disaster_gdacs_realtime"
    job_mode = "realtime"
    source_name = "GDACS Alerts"
    source_code = "disaster_gdacs"
    source_url = "https://www.gdacs.org/gdacsapi/api/Events/geteventlist/SEARCH"
    country = "UNKNOWN"
    language = "en"
    category = "event"
    source_class = "event"

    EVENT_TYPE_TAGS = {
        "EQ": ["earthquake", "disaster", "gdacs"],
        "FL": ["flood", "disaster", "gdacs"],
        "TC": ["tropical_cyclone", "storm", "disaster", "gdacs"],
    }
    ALERT_SEVERITY = {
        "red": 95,
        "orange": 84,
        "green": 62,
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
            "schedule_minutes": 10 if self.job_mode == "realtime" else 1440,
            "priority": 8 if self.job_mode == "realtime" else 3,
            "default_params_json": params.get(self.job_mode) if isinstance(params, dict) and self.job_mode in params else params,
            "notes": None,
        }
        job_profile = resolve_source_job_profile(self.job_name, fallback_job)
        params = job_profile.get("default_params_json") or {}
        raw_event_types = params.get("event_types") or ["EQ", "FL", "TC"]
        self.event_types = [str(value).strip().upper() for value in raw_event_types if str(value).strip()]
        raw_levels = params.get("alert_levels") or ["orange", "red"]
        self.alert_levels = {str(value).strip().lower() for value in raw_levels if str(value).strip()}
        self.relative_days = int(params.get("relative_days") or params.get("replay_window_days") or 7)
        self.page_size = max(1, min(100, int(params.get("pagesize") or 100)))
        self.max_pages = max(1, int(params.get("max_pages") or (4 if self.job_mode == "realtime" else 12)))
        self._geo_extractor = GeoExtractor()
        self._geo_processor = EnhancedGeoProcessor()
        self._job_profile = job_profile
        self._resolved_checkpoint = resolve_source_job_checkpoint(self.job_name) or {}
        self._checkpoint_updated_at = self._coerce_datetime(self._resolved_checkpoint.get("last_seen_source_updated_at"))
        self._checkpoint_external_id = str(self._resolved_checkpoint.get("last_seen_external_id") or "").strip()
        self._query_window = self._build_query_window(params)
        self._checkpoint = {
            "last_success_at": None,
            "last_seen_external_id": None,
            "last_seen_source_updated_at": None,
            "last_event_time": None,
            "last_seen_page": None,
            "last_query_window": self._query_window,
        }

    def start_requests(self) -> Iterator[Request]:
        for event_type in self.event_types:
            yield self._request_page(event_type=event_type, page=1)

    def parse_feed(self, response, **kwargs) -> Iterator[NewsArticle | Request]:
        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError:
            with urllib.request.urlopen(response.url, timeout=20) as remote:
                payload = json.load(remote)

        features = payload.get("features") or []
        event_type = str(response.meta.get("event_type") or "").strip().upper()
        page = int(response.meta.get("page") or 1)
        saw_new_signal = False

        for feature in features:
            if len(self.crawled_items) >= self.max_items:
                break
            item = self._build_item(feature, event_type=event_type)
            if item is None:
                continue
            updated_at = self._coerce_datetime(item.get("source_updated_at"))
            if self.job_mode == "realtime" and self._is_stale_checkpoint_hit(
                updated_at=updated_at,
                external_id=str(item.get("external_id") or "").strip(),
            ):
                continue
            saw_new_signal = True
            self._track_checkpoint(item=item, page=page)
            self.crawled_items.append(item)
            yield item

        has_more = (
            len(features) >= self.page_size
            and page < self.max_pages
            and len(self.crawled_items) < self.max_items
        )
        if has_more and (self.job_mode == "backfill" or saw_new_signal or self._checkpoint_updated_at is None):
            yield self._request_page(event_type=event_type, page=page + 1)

    def _request_page(self, *, event_type: str, page: int) -> Request:
        query = {
            "eventtype": event_type,
            "fromdate": self._query_window["fromdate"],
            "todate": self._query_window["todate"],
            "pagesize": self.page_size,
            "page": page,
            "pagenumber": page,
            "format": "geojson",
        }
        return Request(
            url=f"{self.source_url}?{urlencode(query)}",
            callback=self.parse_feed,
            dont_filter=True,
            meta={"event_type": event_type, "page": page},
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/geo+json, application/json, */*",
            },
        )

    def _build_item(self, feature: dict, *, event_type: str) -> Optional[NewsArticle]:
        properties = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        alert_level = str(properties.get("alertlevel") or "").strip().lower()
        if self.alert_levels and alert_level and alert_level not in self.alert_levels:
            return None

        source_event_type = str(properties.get("eventtype") or event_type or "").strip().upper()
        event_id = str(properties.get("eventid") or "").strip()
        external_id = f"{source_event_type}:{event_id}" if source_event_type and event_id else ""
        if not external_id:
            return None

        title = self._build_title(properties, source_event_type)
        canonical_url = self._canonical_url(properties, source_event_type, event_id)
        source_updated_at = self._parse_gdacs_time(properties.get("datemodified"))
        event_time = self._parse_gdacs_time(properties.get("fromdate")) or source_updated_at
        closed_at = None if self._is_current(properties.get("iscurrent")) else self._parse_gdacs_time(properties.get("todate"))
        event_status = "open" if self._is_current(properties.get("iscurrent")) else "closed"
        display_geo = self._display_geo(geometry)
        bbox = self._bbox_for_feature(feature)
        lat, lng = self._extract_display_point(display_geo)

        description = self.clean_text(properties.get("description") or properties.get("htmldescription") or title) or title
        geo_entities, region_tags = self._derive_geo_entities(
            title=title,
            summary=properties.get("country") or description,
            content=description,
            point_key=f"GDACS:{external_id}",
            point_name=properties.get("country") or title,
            lat=lat,
            lng=lng,
        )
        severity = self._severity_from_properties(properties)
        confidence = self._confidence_from_properties(properties)
        item = NewsArticle()
        item["title"] = title
        item["summary"] = description
        item["content"] = description
        item["url"] = canonical_url
        item["published_at"] = event_time
        item["event_time"] = event_time
        item["event_status"] = event_status
        item["closed_at"] = closed_at
        item["source_updated_at"] = source_updated_at
        item["source_name"] = self.source_name
        item["source_code"] = self.source_code
        item["source_url"] = self.source_url
        item["source_class"] = "event"
        item["crawled_at"] = datetime.now().isoformat()
        item["language"] = self.language
        item["country"] = region_tags[0] if region_tags else self.country
        item["category"] = "disaster"
        item["geo"] = "point" if display_geo and display_geo.get("type") == "Point" else "polygon"
        item["geom_type"] = str(geometry.get("type") or (display_geo.get("type") if display_geo else "Point"))
        item["raw_geometry"] = geometry
        item["display_geo"] = display_geo
        item["bbox"] = bbox
        item["geo_entities"] = geo_entities
        item["region_tags"] = region_tags
        item["severity"] = severity
        item["confidence"] = confidence
        item["canonical_url"] = canonical_url
        item["external_id"] = external_id
        item["tags"] = self._tags_for_event_type(source_event_type)
        item["source_metadata"] = self._build_source_metadata(properties, source_event_type, canonical_url)
        item["heat_score"] = max(severity, 48)
        item["hash"] = self.compute_hash(self.source_code, external_id)
        return item

    def _build_query_window(self, params: dict[str, Any]) -> dict[str, str]:
        now = datetime.now(timezone.utc)
        start = params.get("start")
        end = params.get("end")
        if start and end:
            return {"fromdate": str(start), "todate": str(end)}
        fromdate = (now - timedelta(days=self.relative_days)).strftime("%Y-%m-%d")
        todate = now.strftime("%Y-%m-%d")
        return {"fromdate": fromdate, "todate": todate}

    def _derive_geo_entities(
        self,
        *,
        title: str,
        summary: str,
        content: str,
        point_key: str,
        point_name: str,
        lat: Optional[float],
        lng: Optional[float],
    ) -> tuple[list[dict], list[str]]:
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
                    "name": str(point_name or title)[:100],
                    "geo_key": point_key[:20],
                    "type": "point",
                    "confidence": 0.94,
                    "country_code": country_code or "UNKNOWN",
                    "country_name": country_name,
                    "precision_level": "POINT",
                    "display_mode": "POINT",
                    "geojson_key": point_key[:100],
                    "lat": lat,
                    "lng": lng,
                    "matched_text": str(point_name or title)[:100],
                    "source_text_position": "title",
                    "relevance_score": 0.94,
                    "is_primary": True,
                }
            )
        for entity in normalized_entities[:4]:
            entity["is_primary"] = not entities
            entities.append(entity)
        return entities, region_tags

    def _build_title(self, properties: dict, event_type: str) -> str:
        base = self.clean_text(properties.get("eventname") or properties.get("name") or "")
        country = self.clean_text(properties.get("country") or "")
        alert_level = str(properties.get("alertlevel") or "").strip().upper()
        prefix = f"{alert_level} " if alert_level else ""
        if base and country and country.lower() not in base.lower():
            return f"{prefix}{base} - {country}".strip()
        if base:
            return f"{prefix}{base}".strip()
        type_label = {
            "EQ": "Earthquake",
            "FL": "Flood",
            "TC": "Tropical Cyclone",
        }.get(event_type, "Disaster Alert")
        return self.clean_text(f"{prefix}{type_label} - {country or 'Unknown region'}") or f"{type_label} Alert"

    def _build_source_metadata(self, properties: dict, event_type: str, canonical_url: str) -> dict[str, Any]:
        url_payload = properties.get("url")
        metadata: dict[str, Any] = {
            "role": "alert_enrichment",
            "event_type": event_type,
            "alertlevel": str(properties.get("alertlevel") or "").strip().lower() or None,
            "alertscore": properties.get("alertscore"),
            "episodealertlevel": str(properties.get("episodealertlevel") or "").strip().lower() or None,
            "episodealertscore": properties.get("episodealertscore"),
            "country": self.clean_text(properties.get("country") or ""),
            "iso3": str(properties.get("iso3") or "").strip().upper() or None,
            "source": self.clean_text(properties.get("source") or ""),
            "sourceid": str(properties.get("sourceid") or "").strip() or None,
            "eventid": str(properties.get("eventid") or "").strip() or None,
            "episodeid": str(properties.get("episodeid") or "").strip() or None,
            "iscurrent": self._is_current(properties.get("iscurrent")),
            "severitydata": properties.get("severitydata"),
            "canonical_url": canonical_url,
            "details_url": url_payload.get("details") if isinstance(url_payload, dict) else None,
            "report_url": url_payload.get("report") if isinstance(url_payload, dict) else None,
        }
        return {key: value for key, value in metadata.items() if value not in (None, "", [], {})}

    def _tags_for_event_type(self, event_type: str) -> list[str]:
        return list(self.EVENT_TYPE_TAGS.get(event_type, ["disaster", "gdacs"]))

    def _severity_from_properties(self, properties: dict) -> int:
        alert_level = str(properties.get("alertlevel") or "").strip().lower()
        base = self.ALERT_SEVERITY.get(alert_level, 55)
        try:
            score = float(properties.get("alertscore"))
        except (TypeError, ValueError):
            return base
        if score >= 2:
            return max(base, 96)
        if score >= 1:
            return max(base, 84)
        return max(base, min(72, int(round(55 + score * 10))))

    def _confidence_from_properties(self, properties: dict) -> int:
        alert_level = str(properties.get("alertlevel") or "").strip().lower()
        if alert_level == "red":
            return 92
        if alert_level == "orange":
            return 88
        if alert_level == "green":
            return 80
        return 76

    def _canonical_url(self, properties: dict, event_type: str, event_id: str) -> str:
        raw_url = properties.get("url")
        if isinstance(raw_url, str):
            return raw_url.strip() or f"{self.source_url}?eventtype={event_type}&eventid={event_id}"
        if isinstance(raw_url, dict):
            for key in ("report", "details", "geometry"):
                candidate = raw_url.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()
        return f"{self.source_url}?eventtype={event_type}&eventid={event_id}"

    def _bbox_for_feature(self, feature: dict) -> Optional[list[float]]:
        bbox = feature.get("bbox")
        if isinstance(bbox, list) and len(bbox) == 4:
            try:
                return [float(value) for value in bbox]
            except (TypeError, ValueError):
                return None
        geometry = feature.get("geometry") or {}
        return self._bbox_from_coordinates(geometry.get("coordinates"))

    def _bbox_from_coordinates(self, coordinates: Any) -> Optional[list[float]]:
        points: list[tuple[float, float]] = []

        def _walk(value: Any) -> None:
            if not isinstance(value, list):
                return
            if len(value) >= 2 and all(isinstance(coord, (int, float)) for coord in value[:2]):
                points.append((float(value[0]), float(value[1])))
                return
            for item in value:
                _walk(item)

        _walk(coordinates)
        if not points:
            return None
        lngs = [point[0] for point in points]
        lats = [point[1] for point in points]
        return [min(lngs), min(lats), max(lngs), max(lats)]

    def _display_geo(self, geometry: dict) -> Optional[dict]:
        if not isinstance(geometry, dict):
            return None
        geo_type = str(geometry.get("type") or "").strip()
        if geo_type == "Point":
            coords = geometry.get("coordinates") or []
            if isinstance(coords, list) and len(coords) >= 2:
                return {"type": "Point", "coordinates": [float(coords[0]), float(coords[1])]}
        bbox = self._bbox_from_coordinates(geometry.get("coordinates"))
        if bbox is None:
            return None
        min_lng, min_lat, max_lng, max_lat = bbox
        return {"type": "Point", "coordinates": [round((min_lng + max_lng) / 2, 6), round((min_lat + max_lat) / 2, 6)]}

    def _extract_display_point(self, display_geo: Optional[dict]) -> tuple[Optional[float], Optional[float]]:
        if not isinstance(display_geo, dict):
            return None, None
        coords = display_geo.get("coordinates") or []
        if isinstance(coords, list) and len(coords) >= 2:
            try:
                return float(coords[1]), float(coords[0])
            except (TypeError, ValueError):
                return None, None
        return None, None

    def _is_stale_checkpoint_hit(self, *, updated_at: Optional[datetime], external_id: str) -> bool:
        if updated_at is None or self._checkpoint_updated_at is None:
            return False
        if updated_at < self._checkpoint_updated_at:
            return True
        if updated_at == self._checkpoint_updated_at and external_id == self._checkpoint_external_id:
            return True
        return False

    def _track_checkpoint(self, *, item: NewsArticle, page: int) -> None:
        self._checkpoint["last_success_at"] = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        incoming_updated = self._coerce_datetime(item.get("source_updated_at"))
        current_updated = self._coerce_datetime(self._checkpoint.get("last_seen_source_updated_at"))
        if current_updated is None or (incoming_updated is not None and incoming_updated >= current_updated):
            self._checkpoint["last_seen_external_id"] = item.get("external_id")
            self._checkpoint["last_seen_source_updated_at"] = self._iso_string(item.get("source_updated_at"))
            self._checkpoint["last_event_time"] = self._iso_string(item.get("event_time"))
        self._checkpoint["last_seen_page"] = page
        self._checkpoint["last_query_window"] = dict(self._query_window)

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
                last_seen_page=self._checkpoint["last_seen_page"],
                last_query_window=self._checkpoint["last_query_window"],
            )
        super().closed(reason)

    @staticmethod
    def _is_current(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        normalized = str(value or "").strip().lower()
        return normalized in {"1", "true", "yes", "current", "open"}

    def _parse_gdacs_time(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        parsed = self.parse_datetime(str(value))
        if parsed is None:
            return None
        return parsed.isoformat()

    @staticmethod
    def _coerce_datetime(value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                return None
        return None

    @staticmethod
    def _iso_string(value: Any) -> Optional[str]:
        if isinstance(value, str):
            return value
        if isinstance(value, datetime):
            return value.isoformat()
        return None
