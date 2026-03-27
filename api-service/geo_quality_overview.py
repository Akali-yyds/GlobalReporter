#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import aliased, sessionmaker

from app.database import get_engine
from app.models import EventGeoMapping, GeoEntity, NewsEvent


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 2)


def _build_suspicious_samples(recent_events: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    suspicious_samples: list[dict[str, Any]] = []
    for event in recent_events:
        reasons: list[str] = []
        matched_text = (event.get("matched_text") or "").strip()
        primary_geo_key = event.get("primary_geo_key")

        if not primary_geo_key:
            reasons.append("missing_primary_geo")
        if matched_text and len(matched_text) <= 3:
            reasons.append("short_matched_text")
        if matched_text.isascii() and matched_text.isalpha() and matched_text.islower():
            reasons.append("lowercase_ascii_matched_text")
        if event.get("event_level") == "city" and not primary_geo_key:
            reasons.append("city_event_without_primary_geo")

        if reasons:
            sample = dict(event)
            sample["reasons"] = reasons
            suspicious_samples.append(sample)
        if len(suspicious_samples) >= limit:
            break

    return suspicious_samples


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recent-limit", type=int, default=20)
    parser.add_argument("--suspicious-limit", type=int, default=10)
    args = parser.parse_args()

    engine = get_engine()
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = SessionLocal()

    try:
        primary_mapping = aliased(EventGeoMapping)
        primary_geo = aliased(GeoEntity)

        total_events = db.query(func.count(NewsEvent.id)).scalar() or 0
        total_mappings = db.query(func.count(EventGeoMapping.id)).scalar() or 0
        total_geo_entities = db.query(func.count(GeoEntity.id)).scalar() or 0
        events_with_geo = db.query(func.count(func.distinct(EventGeoMapping.event_id))).scalar() or 0
        events_with_primary_geo = db.query(func.count(func.distinct(EventGeoMapping.event_id))).filter(EventGeoMapping.is_primary.is_(True)).scalar() or 0

        precision_distribution = [
            {"precision_level": level or "UNKNOWN", "count": count}
            for level, count in (
                db.query(GeoEntity.precision_level, func.count(GeoEntity.id))
                .group_by(GeoEntity.precision_level)
                .order_by(func.count(GeoEntity.id).desc())
                .all()
            )
        ]

        extraction_distribution = [
            {"extraction_method": method or "UNKNOWN", "count": count}
            for method, count in (
                db.query(EventGeoMapping.extraction_method, func.count(EventGeoMapping.id))
                .group_by(EventGeoMapping.extraction_method)
                .order_by(func.count(EventGeoMapping.id).desc())
                .all()
            )
        ]

        source_position_distribution = [
            {"source_text_position": position or "UNKNOWN", "count": count}
            for position, count in (
                db.query(EventGeoMapping.source_text_position, func.count(EventGeoMapping.id))
                .group_by(EventGeoMapping.source_text_position)
                .order_by(func.count(EventGeoMapping.id).desc())
                .all()
            )
        ]

        event_level_distribution = [
            {"event_level": level or "UNKNOWN", "count": count}
            for level, count in (
                db.query(NewsEvent.event_level, func.count(NewsEvent.id))
                .group_by(NewsEvent.event_level)
                .order_by(func.count(NewsEvent.id).desc())
                .all()
            )
        ]

        top_main_countries = [
            {"main_country": country or "UNKNOWN", "count": count}
            for country, count in (
                db.query(NewsEvent.main_country, func.count(NewsEvent.id))
                .group_by(NewsEvent.main_country)
                .order_by(func.count(NewsEvent.id).desc())
                .limit(10)
                .all()
            )
        ]

        recent_events = []
        rows = (
            db.query(NewsEvent, primary_mapping, primary_geo)
            .outerjoin(
                primary_mapping,
                (primary_mapping.event_id == NewsEvent.id) & (primary_mapping.is_primary.is_(True)),
            )
            .outerjoin(primary_geo, primary_geo.id == primary_mapping.geo_id)
            .order_by(NewsEvent.created_at.desc())
            .limit(max(args.recent_limit, 1))
            .all()
        )
        for event, mapping, geo in rows:
            recent_events.append(
                {
                    "event_id": event.id,
                    "title": event.title,
                    "main_country": event.main_country,
                    "event_level": event.event_level,
                    "created_at": event.created_at,
                    "primary_geo_key": mapping.geo_key if mapping else None,
                    "primary_geo_name": geo.name if geo else None,
                    "primary_geo_type": (geo.precision_level or "").upper() if geo else None,
                    "matched_text": mapping.matched_text if mapping else None,
                }
            )

        suspicious_samples = _build_suspicious_samples(recent_events, max(args.suspicious_limit, 1))

        output = {
            "summary": {
                "total_events": total_events,
                "events_with_geo": events_with_geo,
                "events_without_geo": max(total_events - events_with_geo, 0),
                "geo_coverage_rate_pct": _ratio(events_with_geo, total_events),
                "events_with_primary_geo": events_with_primary_geo,
                "primary_geo_coverage_rate_pct": _ratio(events_with_primary_geo, total_events),
                "total_geo_entities": total_geo_entities,
                "total_event_geo_mappings": total_mappings,
            },
            "precision_distribution": precision_distribution,
            "event_level_distribution": event_level_distribution,
            "extraction_distribution": extraction_distribution,
            "source_position_distribution": source_position_distribution,
            "top_main_countries": top_main_countries,
            "suspicious_samples": suspicious_samples,
            "recent_events": recent_events,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2, default=_json_default))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
