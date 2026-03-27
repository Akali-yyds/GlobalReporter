#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session, sessionmaker

from app.api.news import get_event_detail
from app.database import get_engine
from app.models import EventGeoMapping, GeoEntity, NewsEvent
from app.services.news_ingest import ingest_crawled_articles

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


class RollbackSession(Session):
    def commit(self) -> None:
        self.flush()


def build_payload(seed: str) -> dict[str, Any]:
    return {
        "title": f"Geo smoke validation {seed} Canada officials in London discuss manufacturing",
        "summary": "Ontario leaders met investors in London.",
        "content": "Canada signaled support for factories near London, Ontario.",
        "url": f"https://example.com/geo-smoke/{seed}",
        "source_name": "Geo Smoke Test",
        "source_code": "geo_smoke",
        "source_url": "https://example.com",
        "language": "en",
        "country": "CA",
        "category": "business",
        "heat_score": 42,
        "hash": f"geo-smoke-{seed}",
        "region_tags": ["CA"],
        "geo_entities": [
            {
                "name": "London",
                "geo_key": "CA:6058560",
                "type": "city",
                "confidence": 0.97,
                "country_code": "CA",
                "country_name": "Canada",
                "admin1_code": "08",
                "admin1_name": "Ontario",
                "city_name": "London",
                "precision_level": "CITY",
                "display_mode": "POINT",
                "geojson_key": "CA:6058560",
                "lat": 42.98339,
                "lng": -81.23304,
                "matched_text": "London",
                "source_text_position": "title",
                "relevance_score": 0.97,
                "is_primary": True,
            },
            {
                "name": "Canada",
                "geo_key": "CA",
                "type": "country",
                "confidence": 0.91,
                "country_code": "CA",
                "country_name": "Canada",
                "precision_level": "COUNTRY",
                "display_mode": "POLYGON",
                "geojson_key": "CA",
                "lat": 45.41117,
                "lng": -75.69812,
                "matched_text": "Canada",
                "source_text_position": "title",
                "relevance_score": 0.91,
                "is_primary": False,
            },
        ],
    }


def validate_detail_payload(detail: dict[str, Any]) -> None:
    if detail.get("main_country") != "CA":
        raise RuntimeError(f"Unexpected main_country: {detail.get('main_country')}")
    if detail.get("event_level") != "city":
        raise RuntimeError(f"Unexpected event_level: {detail.get('event_level')}")

    geo_mappings = detail.get("geo_mappings") or []
    if len(geo_mappings) < 2:
        raise RuntimeError(f"Expected at least 2 geo mappings, got {len(geo_mappings)}")

    primary_geo = next((item for item in geo_mappings if item.get("is_primary")), None)
    if not primary_geo:
        raise RuntimeError("Primary geo mapping was not found")
    if primary_geo.get("geo_key") != "CA:6058560":
        raise RuntimeError(f"Unexpected primary geo_key: {primary_geo.get('geo_key')}")
    if primary_geo.get("geo_type") != "city":
        raise RuntimeError(f"Unexpected primary geo_type: {primary_geo.get('geo_type')}")
    if primary_geo.get("display_type") != "point":
        raise RuntimeError(f"Unexpected primary display_type: {primary_geo.get('display_type')}")
    if primary_geo.get("matched_text") != "London":
        raise RuntimeError(f"Unexpected primary matched_text: {primary_geo.get('matched_text')}")


def run_smoke(commit: bool) -> dict[str, Any]:
    seed = uuid4().hex[:16]
    payload = build_payload(seed)
    engine = get_engine()
    session_cls = Session if commit else RollbackSession
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=session_cls)
    db = SessionLocal()

    try:
        ingest_result = ingest_crawled_articles(db, [payload])

        event = db.query(NewsEvent).filter(NewsEvent.title == payload["title"]).first()
        if event is None:
            raise RuntimeError("NewsEvent was not created")

        mappings = db.query(EventGeoMapping).filter(EventGeoMapping.event_id == event.id).all()
        geo_records = db.query(GeoEntity).filter(GeoEntity.geo_key.in_(["CA:6058560", "CA"])) .all()
        detail = asyncio.run(get_event_detail(event.id, db))
        validate_detail_payload(detail)

        output = {
            "mode": "commit" if commit else "rollback",
            "event_id": event.id,
            "title": event.title,
            "main_country": event.main_country,
            "event_level": event.event_level,
            "ingest_result": ingest_result,
            "mapping_count": len(mappings),
            "geo_entity_count": len(geo_records),
            "detail": detail,
        }

        if commit:
            db.commit()
        else:
            db.rollback()

        return output
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()

    try:
        result = run_smoke(commit=args.commit)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=_json_default))
        if args.commit:
            logger.info("Smoke validation completed and committed.")
        else:
            logger.info("Smoke validation completed and rolled back.")
        return 0
    except Exception as exc:
        logger.exception("Smoke validation failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
