"""
Globe API endpoints.
"""
from collections import defaultdict
from typing import Any, Dict, DefaultDict, List, Optional, Tuple

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models import NewsEvent, EventGeoMapping, GeoEntity
from app.schemas.event import NewsEventListItem
from app.utils.ttl_cache import globe_hotspot_cache

router = APIRouter()

# ISO 3166-1 alpha-2 -> alpha-3 (Natural Earth polygons use ISO_A3)
_ISO2_TO_ISO3: Dict[str, str] = {
    "CN": "CHN",
    "US": "USA",
    "GB": "GBR",
    "JP": "JPN",
    "KR": "KOR",
    "TW": "TWN",
    "HK": "HKG",
    "DE": "DEU",
    "FR": "FRA",
    "IN": "IND",
    "RU": "RUS",
    "AU": "AUS",
    "CA": "CAN",
    "BR": "BRA",
    "IT": "ITA",
    "ES": "ESP",
    "MX": "MEX",
    "SA": "SAU",
    "AE": "ARE",
    "SG": "SGP",
    "NL": "NLD",
    "SE": "SWE",
    "NO": "NOR",
    "PL": "POL",
    "TR": "TUR",
    "ID": "IDN",
    "VN": "VNM",
    "TH": "THA",
    "MY": "MYS",
    "PH": "PHL",
    "EG": "EGY",
    "ZA": "ZAF",
    "NG": "NGA",
    "AR": "ARG",
    "CL": "CHL",
    "CO": "COL",
    "PT": "PRT",
    "CH": "CHE",
    "AT": "AUT",
    "BE": "BEL",
    "IE": "IRL",
    "FI": "FIN",
    "DK": "DNK",
    "NZ": "NZL",
    "IL": "ISR",
    "UA": "UKR",
    "IR": "IRN",
    "IQ": "IRQ",
    "PK": "PAK",
    "BD": "BGD",
    "UNKNOWN": "",
}

# Approximate country centers [lng, lat] for point markers when no GeoEntity lat/lng
_ISO2_CENTER: Dict[str, Tuple[float, float]] = {
    "CN": (104.2, 35.9),
    "US": (-98.35, 39.5),
    "GB": (-2.5, 54.5),
    "JP": (138.25, 36.2),
    "KR": (127.77, 35.9),
    "TW": (121.0, 23.7),
    "HK": (114.17, 22.32),
    "DE": (10.45, 51.16),
    "FR": (2.21, 46.23),
    "IN": (78.96, 20.59),
    "RU": (105.32, 61.52),
    "AU": (133.78, -25.27),
    "CA": (-106.35, 56.13),
    "BR": (-51.93, -14.24),
    "IT": (12.57, 41.87),
    "ES": (-3.75, 40.46),
    "MX": (-102.55, 23.63),
    "SA": (45.08, 23.89),
    "AE": (53.85, 23.42),
    "SG": (103.82, 1.35),
    "NL": (5.29, 52.13),
    "SE": (18.64, 60.13),
    "NO": (8.47, 60.47),
    "PL": (19.15, 51.92),
    "TR": (35.24, 38.96),
    "ID": (113.92, -0.79),
    "VN": (108.28, 14.06),
    "TH": (100.99, 15.87),
    "MY": (101.98, 4.21),
    "PH": (122.56, 11.78),
    "EG": (30.8, 26.82),
    "ZA": (25.75, -29.0),
    "NG": (8.68, 9.08),
    "AR": (-63.62, -38.42),
    "CL": (-71.54, -35.68),
    "CO": (-74.3, 4.57),
    "PT": (-8.22, 39.4),
    "CH": (8.23, 46.82),
    "AT": (14.55, 47.52),
    "BE": (4.47, 50.5),
    "IE": (-8.24, 53.41),
    "FI": (25.75, 61.92),
    "DK": (9.5, 56.26),
    "NZ": (172.64, -41.5),
    "IL": (34.85, 31.05),
    "UA": (31.16, 48.38),
    "IR": (53.69, 32.43),
    "IQ": (43.68, 33.22),
    "PK": (69.35, 29.97),
    "BD": (90.36, 23.68),
}

_ISO2_NAME: Dict[str, str] = {
    "CN": "中国",
    "US": "美国",
    "GB": "英国",
    "JP": "日本",
    "KR": "韩国",
    "TW": "台湾",
    "HK": "香港",
    "DE": "德国",
    "FR": "法国",
    "IN": "印度",
    "RU": "俄罗斯",
    "AU": "澳大利亚",
    "CA": "加拿大",
    "BR": "巴西",
    "UNKNOWN": "未知地区",
}


def _iso3_from_geo(geo: GeoEntity) -> Optional[str]:
    cc = (geo.country_code or "").upper()
    if len(cc) == 3 and cc.isalpha():
        return cc
    return _ISO2_TO_ISO3.get(cc)


def _geo_type_from_precision(geo: GeoEntity) -> str:
    precision_level = (geo.precision_level or "").upper()
    if precision_level == "ADMIN1":
        return "admin1"
    if precision_level == "CITY":
        return "city"
    return "country"


def _display_type_from_geo(geo: GeoEntity) -> str:
    display_mode = (geo.display_mode or "").upper()
    if display_mode == "POINT":
        return "point"
    if display_mode == "LIST_ONLY":
        return "list_only"
    return "polygon"


def _fallback_hotspot(event: NewsEvent) -> Optional[Dict[str, Any]]:
    mc = (event.main_country or "UNKNOWN").upper()
    center = _ISO2_CENTER.get(mc)
    iso3 = _ISO2_TO_ISO3.get(mc)
    if not center or not iso3:
        return None
    name = _ISO2_NAME.get(mc, mc)
    return {
        "event_id": event.id,
        "geo_key": mc,
        "geo_name": name,
        "geo_type": "country",
        "display_type": "point",
        "heat_score": event.heat_score,
        "confidence": 0.45,
        "title": event.title,
        "summary": event.summary,
        "center": [center[0], center[1]],
        "iso_a3": iso3,
    }


@router.get("/hotspots")
async def get_hotspots(
    scope: Optional[str] = Query(None, pattern="^(all|china|world)$"),
    min_heat: Optional[int] = Query(None, ge=0),
    limit: Optional[int] = Query(50, ge=1, le=500),
    since_hours: Optional[int] = Query(None, ge=1, le=168, description="Only return events seen within last N hours"),
    db: Session = Depends(get_db),
):
    """
    Get hotspots for globe visualization.
    Returns aggregated hotspot data with geographic information.
    """
    query = db.query(NewsEvent)

    # Apply scope filter
    if scope == "china":
        query = query.filter(NewsEvent.main_country.in_(["CN", "TW", "HK"]))
    elif scope == "world":
        query = query.filter(~NewsEvent.main_country.in_(["CN", "TW", "HK", "UNKNOWN"]))

    # Apply heat filter
    if min_heat:
        query = query.filter(NewsEvent.heat_score >= min_heat)

    # Apply time window filter (today-only globe mode)
    if since_hours:
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=since_hours)
        query = query.filter(NewsEvent.last_seen_at >= cutoff)

    # Check cache first
    cache_key = f"globe_hotspots:{scope}:{min_heat}:{limit}:{since_hours}"
    hit, cached = globe_hotspot_cache.get(cache_key)
    if hit:
        return cached

    # Get top events
    events = query.order_by(desc(NewsEvent.heat_score)).limit(limit).all()

    if not events:
        result = {"hotspots": []}
        globe_hotspot_cache.set(cache_key, result)
        return result

    event_ids = [e.id for e in events]

    # Batch-fetch all EventGeoMapping + GeoEntity rows in one JOIN (avoids N+1)
    rows = (
        db.query(EventGeoMapping, GeoEntity)
        .join(GeoEntity, GeoEntity.id == EventGeoMapping.geo_id)
        .filter(EventGeoMapping.event_id.in_(event_ids))
        .all()
    )

    # Group mapping+geo rows by event_id
    event_geo_rows: DefaultDict[str, List[Tuple[EventGeoMapping, GeoEntity]]] = defaultdict(list)
    for mapping, geo in rows:
        event_geo_rows[mapping.event_id].append((mapping, geo))

    # Build hotspots (geo mappings + fallback from main_country for events with no geo)
    hotspots: List[Dict[str, Any]] = []
    for event in events:
        event_rows: List[Dict[str, Any]] = []
        for mapping, geo in event_geo_rows.get(event.id, []):
            iso3 = _iso3_from_geo(geo)
            center: Optional[List[float]] = None
            if geo.lat is not None and geo.lng is not None:
                center = [float(geo.lng), float(geo.lat)]
            else:
                cc = (geo.country_code or "").upper()
                c = _ISO2_CENTER.get(cc)
                if c:
                    center = [c[0], c[1]]
                    if not iso3:
                        iso3 = _ISO2_TO_ISO3.get(cc)

            if not iso3:
                cc2 = (geo.country_code or "").upper()
                iso3 = _ISO2_TO_ISO3.get(cc2)

            if not center:
                continue

            event_rows.append(
                {
                    "event_id": event.id,
                    "geo_key": mapping.geo_key,
                    "geo_name": geo.name,
                    "geo_type": _geo_type_from_precision(geo),
                    "display_type": _display_type_from_geo(geo),
                    "heat_score": event.heat_score,
                    "confidence": float(mapping.confidence or 1.0),
                    "title": event.title,
                    "summary": event.summary,
                    "center": center,
                    "iso_a3": iso3,
                }
            )

        if not event_rows:
            fb = _fallback_hotspot(event)
            if fb:
                hotspots.append(fb)
        else:
            hotspots.extend(event_rows)

    result = {"hotspots": hotspots}
    globe_hotspot_cache.set(cache_key, result)
    return result


@router.get("/regions/{geo_key}/news")
async def get_region_news(
    geo_key: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    since_hours: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_db),
):
    """Get news for a specific region."""
    # A1:CC:code keys cannot be matched via EventGeoMapping.geo_key (stored as US.NM / US:geonames_id).
    # Join through GeoEntity instead to find events by country_code + admin1_code.
    if geo_key.startswith('A1:'):
        parts = geo_key.split(':', 2)
        if len(parts) == 3:
            cc, a1 = parts[1].upper(), parts[2]
            event_ids = (
                db.query(EventGeoMapping.event_id)
                .join(GeoEntity, GeoEntity.id == EventGeoMapping.geo_id)
                .filter(GeoEntity.country_code == cc)
                .filter(GeoEntity.admin1_code == a1)
                .distinct()
                .subquery()
            )
        else:
            event_ids = db.query(EventGeoMapping.event_id).filter(
                EventGeoMapping.geo_key == geo_key
            ).distinct().subquery()
    else:
        event_ids = db.query(EventGeoMapping.event_id).filter(
            EventGeoMapping.geo_key == geo_key
        ).distinct().subquery()

    query = db.query(NewsEvent).filter(NewsEvent.id.in_(event_ids))
    if since_hours is not None:
        cutoff = datetime.utcnow() - timedelta(hours=since_hours)
        query = query.filter(NewsEvent.last_seen_at >= cutoff)
    total = query.count()

    offset = (page - 1) * page_size
    events = query.order_by(desc(NewsEvent.heat_score)).offset(offset).limit(page_size).all()

    items = [NewsEventListItem.model_validate(e).model_dump() for e in events]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }
