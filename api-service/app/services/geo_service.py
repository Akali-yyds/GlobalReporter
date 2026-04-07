"""
GeoService - geographic aggregation and hotspot queries.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import case, func, literal

from app.models import NewsEvent, EventGeoMapping, GeoEntity

# ISO 3166-1 alpha-2 -> alpha-3
_ISO2_TO_ISO3: Dict[str, str] = {
    "CN": "CHN", "US": "USA", "GB": "GBR", "JP": "JPN", "KR": "KOR",
    "TW": "TWN", "HK": "HKG", "DE": "DEU", "FR": "FRA", "IN": "IND",
    "RU": "RUS", "AU": "AUS", "CA": "CAN", "BR": "BRA", "IT": "ITA",
    "ES": "ESP", "MX": "MEX", "SA": "SAU", "AE": "ARE", "SG": "SGP",
    "NL": "NLD", "SE": "SWE", "NO": "NOR", "PL": "POL", "TR": "TUR",
    "ID": "IDN", "VN": "VNM", "TH": "THA", "MY": "MYS", "PH": "PHL",
    "EG": "EGY", "ZA": "ZAF", "NG": "NGA", "AR": "ARG", "CL": "CHL",
    "CO": "COL", "PT": "PRT", "CH": "CHE", "AT": "AUT", "BE": "BEL",
    "IE": "IRL", "FI": "FIN", "DK": "DNK", "NZ": "NZL", "IL": "ISR",
    "UA": "UKR", "IR": "IRN", "IQ": "IRQ", "PK": "PAK", "BD": "BGD",
    "CZ": "CZE", "HU": "HUN", "RO": "ROU", "GR": "GRC", "SK": "SVK",
    "HR": "HRV", "BG": "BGR", "RS": "SRB", "LT": "LTU", "LV": "LVA",
    "EE": "EST", "SI": "SVN", "KZ": "KAZ", "UZ": "UZB", "GE": "GEO",
    "AM": "ARM", "AZ": "AZE", "BY": "BLR", "MD": "MDA", "MN": "MNG",
    "KP": "PRK", "MM": "MMR", "KH": "KHM", "LA": "LAO", "NP": "NPL",
    "LK": "LKA", "AF": "AFG", "IQ": "IRQ", "SY": "SYR", "YE": "YEM",
    "JO": "JOR", "LB": "LBN", "KW": "KWT", "QA": "QAT", "OM": "OMN",
    "MA": "MAR", "DZ": "DZA", "TN": "TUN", "LY": "LBY", "ET": "ETH",
    "KE": "KEN", "TZ": "TZA", "UG": "UGA", "GH": "GHA", "CI": "CIV",
    "CM": "CMR", "SN": "SEN", "MZ": "MOZ", "MG": "MDG", "AO": "AGO",
    "ZM": "ZMB", "ZW": "ZWE", "VE": "VEN", "PE": "PER", "EC": "ECU",
    "BO": "BOL", "PY": "PRY", "UY": "URY",
}

# Approximate country centers [lng, lat]
_ISO2_CENTER: Dict[str, Tuple[float, float]] = {
    "CN": (104.2, 35.9), "US": (-98.35, 39.5), "GB": (-2.5, 54.5),
    "JP": (138.25, 36.2), "KR": (127.77, 35.9), "TW": (121.0, 23.7),
    "HK": (114.17, 22.32), "DE": (10.45, 51.16), "FR": (2.21, 46.23),
    "IN": (78.96, 20.59), "RU": (105.32, 61.52), "AU": (133.78, -25.27),
    "CA": (-106.35, 56.13), "BR": (-51.93, -14.24), "IT": (12.57, 41.87),
    "ES": (-3.75, 40.46), "MX": (-102.55, 23.63), "SA": (45.08, 23.89),
    "AE": (53.85, 23.42), "SG": (103.82, 1.35), "NL": (5.29, 52.13),
    "SE": (18.64, 60.13), "NO": (8.47, 60.47), "PL": (19.15, 51.92),
    "TR": (35.24, 38.96), "ID": (113.92, -0.79), "VN": (108.28, 14.06),
    "TH": (100.99, 15.87), "MY": (101.98, 4.21), "PH": (122.56, 11.78),
    "EG": (30.8, 26.82), "ZA": (25.75, -29.0), "NG": (8.68, 9.08),
    "AR": (-63.62, -38.42), "CL": (-71.54, -35.68), "CO": (-74.3, 4.57),
    "PT": (-8.22, 39.4), "CH": (8.23, 46.82), "AT": (14.55, 47.52),
    "BE": (4.47, 50.5), "IE": (-8.24, 53.41), "FI": (25.75, 61.92),
    "DK": (9.5, 56.26), "NZ": (172.64, -41.5), "IL": (34.85, 31.05),
    "UA": (31.16, 48.38), "IR": (53.69, 32.43), "IQ": (43.68, 33.22),
    "PK": (69.35, 29.97), "BD": (90.36, 23.68), "UA": (31.16, 48.38),
}

# ISO2 -> display name (Chinese)
_ISO2_NAME: Dict[str, str] = {
    "CN": "中国", "US": "美国", "GB": "英国", "JP": "日本", "KR": "韩国",
    "TW": "台湾", "HK": "香港", "DE": "德国", "FR": "法国", "IN": "印度",
    "RU": "俄罗斯", "AU": "澳大利亚", "CA": "加拿大", "BR": "巴西",
    "IT": "意大利", "ES": "西班牙", "MX": "墨西哥", "SA": "沙特阿拉伯",
    "AE": "阿联酋", "SG": "新加坡", "NL": "荷兰", "SE": "瑞典",
    "NO": "挪威", "PL": "波兰", "TR": "土耳其", "ID": "印度尼西亚",
    "VN": "越南", "TH": "泰国", "MY": "马来西亚", "PH": "菲律宾",
    "EG": "埃及", "ZA": "南非", "NG": "尼日利亚", "AR": "阿根廷",
    "CL": "智利", "CO": "哥伦比亚", "PT": "葡萄牙", "CH": "瑞士",
    "AT": "奥地利", "BE": "比利时", "IE": "爱尔兰", "FI": "芬兰",
    "DK": "丹麦", "NZ": "新西兰", "IL": "以色列", "UA": "乌克兰",
    "IR": "伊朗", "IQ": "伊拉克", "PK": "巴基斯坦", "BD": "孟加拉国",
}

_CHINA_ALIAS_ISO2 = {"TW"}
_CHINA_REGION_CODES = {"CN", "TW"}
_CHINA_TAIWAN_ADMIN1_CODE = "TW"
_CHINA_TAIWAN_ADMIN1_NAME = "Taiwan"


def get_country_hotspots(
    db: Session,
    scope: Optional[str] = None,
    limit: int = 80,
    min_heat: Optional[int] = None,
    since_hours: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Aggregate event heat by country.
    Returns one row per country sorted by total heat descending.
    Avoids double-counting events mapped to multiple entities in the same country.
    """
    # Sub-query: distinct (event_id, country_code) pairs with their heat_score
    event_q = db.query(NewsEvent)
    if since_hours:
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=since_hours)
        event_q = event_q.filter(NewsEvent.last_seen_at >= cutoff)

    normalized_country_code = case(
        (GeoEntity.country_code.in_(_CHINA_ALIAS_ISO2), literal("CN")),
        else_=GeoEntity.country_code,
    )
    normalized_country_name = case(
        (GeoEntity.country_code.in_(_CHINA_ALIAS_ISO2), literal("China")),
        else_=GeoEntity.country_name,
    )

    subq = (
        db.query(
            normalized_country_code.label("country_code"),
            normalized_country_name.label("country_name"),
            NewsEvent.id.label("event_id"),
            NewsEvent.heat_score,
        )
        .join(EventGeoMapping, EventGeoMapping.geo_id == GeoEntity.id)
        .join(NewsEvent, NewsEvent.id == EventGeoMapping.event_id)
        .filter(NewsEvent.id.in_(event_q.with_entities(NewsEvent.id)))
        .distinct()
        .subquery()
    )

    agg_q = (
        db.query(
            subq.c.country_code,
            func.max(subq.c.country_name).label("country_name"),
            func.sum(subq.c.heat_score).label("heat_total"),
            func.count(subq.c.event_id).label("event_count"),
        )
        .group_by(subq.c.country_code)
    )

    if scope == "china":
        agg_q = agg_q.filter(subq.c.country_code.in_(["CN", "HK"]))
    elif scope == "world":
        agg_q = agg_q.filter(~subq.c.country_code.in_(["CN", "HK"]))

    if min_heat is not None:
        agg_q = agg_q.having(func.sum(subq.c.heat_score) >= min_heat)

    rows = (
        agg_q
        .order_by(func.sum(subq.c.heat_score).desc())
        .limit(limit)
        .all()
    )

    result: List[Dict[str, Any]] = []
    for row in rows:
        cc = (row.country_code or "").upper()
        center = _ISO2_CENTER.get(cc)
        display_name = row.country_name or _ISO2_NAME.get(cc, cc)
        result.append({
            "country_code": cc,
            "country_name": display_name,
            "iso_a3": _ISO2_TO_ISO3.get(cc),
            "heat_total": int(row.heat_total or 0),
            "event_count": int(row.event_count or 0),
            "center": list(center) if center else None,
        })

    return result


def get_admin1_hotspots(
    db: Session,
    country_code: str,
    limit: int = 50,
    since_hours: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Aggregate event heat by admin1 within a country.
    Returns one row per admin1 sorted by total heat descending.
    Also includes a center coordinate looked up from the best matching GeoEntity.
    """
    cc = country_code.upper()

    event_q = db.query(NewsEvent.id)
    if since_hours:
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=since_hours)
        event_q = event_q.filter(NewsEvent.last_seen_at >= cutoff)

    # Sub-query: distinct (event_id, admin1_code) pairs with heat_score
    subq = (
        db.query(
            GeoEntity.admin1_code,
            GeoEntity.admin1_name,
            NewsEvent.id.label("event_id"),
            NewsEvent.heat_score,
        )
        .join(EventGeoMapping, EventGeoMapping.geo_id == GeoEntity.id)
        .join(NewsEvent, NewsEvent.id == EventGeoMapping.event_id)
        .filter(
            GeoEntity.country_code == cc,
            GeoEntity.admin1_code.isnot(None),
            NewsEvent.id.in_(event_q),
        )
        .distinct()
        .subquery()
    )

    rows = (
        db.query(
            subq.c.admin1_code,
            func.max(subq.c.admin1_name).label("admin1_name"),
            func.sum(subq.c.heat_score).label("heat_total"),
            func.count(subq.c.event_id).label("event_count"),
        )
        .group_by(subq.c.admin1_code)
        .order_by(func.sum(subq.c.heat_score).desc())
        .limit(limit)
        .all()
    )

    # Build admin1_code -> GeoEntity lookup for center coordinates
    admin1_codes = [r.admin1_code for r in rows if r.admin1_code]
    geo_centers: Dict[str, Tuple[float, float]] = {}
    geo_keys: Dict[str, str] = {}
    if admin1_codes:
        admin1_entities = (
            db.query(GeoEntity)
            .filter(
                GeoEntity.country_code == cc,
                GeoEntity.admin1_code.in_(admin1_codes),
                GeoEntity.precision_level == "ADMIN1",
                GeoEntity.lat.isnot(None),
                GeoEntity.lng.isnot(None),
            )
            .all()
        )
        for ge in admin1_entities:
            if ge.admin1_code and ge.admin1_code not in geo_centers:
                geo_centers[ge.admin1_code] = (float(ge.lng), float(ge.lat))
                geo_keys[ge.admin1_code] = ge.geo_key

    result: List[Dict[str, Any]] = []
    for row in rows:
        a1 = row.admin1_code
        center = geo_centers.get(a1) if a1 else None
        result.append({
            "admin1_code": a1,
            "admin1_name": row.admin1_name,
            "geo_key": geo_keys.get(a1) if a1 else None,
            "heat_total": int(row.heat_total or 0),
            "event_count": int(row.event_count or 0),
            "center": list(center) if center else None,
        })

    if cc == "CN" and not any(item.get("admin1_code") == _CHINA_TAIWAN_ADMIN1_CODE for item in result):
        tw_subq = (
            db.query(
                NewsEvent.id.label("event_id"),
                NewsEvent.heat_score,
            )
            .join(EventGeoMapping, EventGeoMapping.event_id == NewsEvent.id)
            .join(GeoEntity, GeoEntity.id == EventGeoMapping.geo_id)
            .filter(
                GeoEntity.country_code == "TW",
                NewsEvent.id.in_(event_q),
            )
            .distinct()
            .subquery()
        )

        tw_row = (
            db.query(
                func.sum(tw_subq.c.heat_score).label("heat_total"),
                func.count(tw_subq.c.event_id).label("event_count"),
            )
            .one()
        )

        if int(tw_row.event_count or 0) > 0:
            tw_center = _ISO2_CENTER.get("TW")
            result.append({
                "admin1_code": _CHINA_TAIWAN_ADMIN1_CODE,
                "admin1_name": _CHINA_TAIWAN_ADMIN1_NAME,
                "geo_key": f"A1:CN:{_CHINA_TAIWAN_ADMIN1_CODE}",
                "heat_total": int(tw_row.heat_total or 0),
                "event_count": int(tw_row.event_count or 0),
                "center": list(tw_center) if tw_center else None,
            })

    result.sort(key=lambda item: item["heat_total"], reverse=True)
    result = result[:limit]

    return result


def get_city_hotspots(
    db: Session,
    country_code: str,
    limit: int = 30,
    min_heat: Optional[int] = None,
    since_hours: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Aggregate event heat by city within a country.
    Only returns cities that have lat/lng coordinates.
    Sorted by total heat descending.
    """
    cc = country_code.upper()

    event_q = db.query(NewsEvent.id)
    if since_hours:
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=since_hours)
        event_q = event_q.filter(NewsEvent.last_seen_at >= cutoff)

    subq = (
        db.query(
            GeoEntity.id.label("geo_id"),
            GeoEntity.name.label("city_name"),
            GeoEntity.geo_key,
            GeoEntity.lat,
            GeoEntity.lng,
            GeoEntity.admin1_name,
            NewsEvent.id.label("event_id"),
            NewsEvent.heat_score,
        )
        .join(EventGeoMapping, EventGeoMapping.geo_id == GeoEntity.id)
        .join(NewsEvent, NewsEvent.id == EventGeoMapping.event_id)
        .filter(
            GeoEntity.country_code == cc,
            GeoEntity.precision_level == "CITY",
            GeoEntity.lat.isnot(None),
            GeoEntity.lng.isnot(None),
            NewsEvent.id.in_(event_q),
        )
        .distinct()
        .subquery()
    )

    agg_q = (
        db.query(
            subq.c.geo_id,
            func.max(subq.c.city_name).label("city_name"),
            func.max(subq.c.geo_key).label("geo_key"),
            func.max(subq.c.lat).label("lat"),
            func.max(subq.c.lng).label("lng"),
            func.max(subq.c.admin1_name).label("admin1_name"),
            func.sum(subq.c.heat_score).label("heat_total"),
            func.count(subq.c.event_id).label("event_count"),
        )
        .group_by(subq.c.geo_id)
    )

    if min_heat is not None:
        agg_q = agg_q.having(func.sum(subq.c.heat_score) >= min_heat)

    rows = (
        agg_q
        .order_by(func.sum(subq.c.heat_score).desc())
        .limit(limit)
        .all()
    )

    result: List[Dict[str, Any]] = []
    for row in rows:
        result.append({
            "city_name": row.city_name,
            "admin1_name": row.admin1_name,
            "geo_key": row.geo_key,
            "heat_total": int(row.heat_total or 0),
            "event_count": int(row.event_count or 0),
            "center": [float(row.lng), float(row.lat)],
        })

    return result
