#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import sessionmaker

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(ROOT_DIR, ".."))
CRAWLER_DIR = os.path.join(PROJECT_ROOT, "crawler-service")
if CRAWLER_DIR not in sys.path:
    sys.path.insert(0, CRAWLER_DIR)

from news_crawler.pipelines import GeoExtractionPipeline

from app.database import get_engine
from app.models import EventArticle, NewsArticle, NewsEvent
from app.services.news_ingest import _normalize_geo_type, _sync_event_geo_mappings


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def _build_item(article: NewsArticle) -> dict[str, Any]:
    return {
        "title": article.title,
        "summary": article.summary,
        "content": article.content,
        "url": article.article_url,
        "source_name": article.source_name,
        "source_code": article.source_code,
        "source_url": article.source_url,
        "language": article.language,
    }


def _select_article_for_event(db, event_id: str) -> NewsArticle | None:
    row = (
        db.query(NewsArticle)
        .join(EventArticle, EventArticle.article_id == NewsArticle.id)
        .filter(EventArticle.event_id == event_id)
        .order_by(desc(NewsArticle.heat_score), desc(NewsArticle.crawl_time))
        .first()
    )
    return row


def _extract_with_pipeline(pipeline: GeoExtractionPipeline, article: NewsArticle) -> tuple[list[dict[str, Any]], list[str]]:
    item = _build_item(article)
    processed = pipeline.process_item(item, None)
    geo_entities = processed.get("geo_entities") or []
    region_tags = processed.get("region_tags") or []
    return geo_entities, region_tags


def _apply_event_geo(event: NewsEvent, article: NewsArticle, geo_entities: list[dict[str, Any]], region_tags: list[str]) -> None:
    article.region_tags = region_tags
    if not geo_entities:
        return

    primary_geo = geo_entities[0]
    event.main_country = (primary_geo.get("country_code") or event.main_country or "UNKNOWN")[:10]
    event.event_level = (_normalize_geo_type(primary_geo.get("type")) or event.event_level or "country")[:20]
    if region_tags:
        event.main_country = region_tags[0][:10]


def run(limit: int, commit: bool, event_id: str | None) -> dict[str, Any]:
    engine = get_engine()
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = SessionLocal()
    pipeline = GeoExtractionPipeline()

    try:
        query = db.query(NewsEvent)
        if event_id:
            query = query.filter(NewsEvent.id == event_id)
        events = query.order_by(desc(NewsEvent.last_seen_at)).limit(limit).all()

        scanned = 0
        extracted = 0
        updated = 0
        skipped = 0
        details: list[dict[str, Any]] = []

        for event in events:
            scanned += 1
            article = _select_article_for_event(db, event.id)
            if article is None:
                skipped += 1
                details.append(
                    {
                        "event_id": event.id,
                        "title": event.title,
                        "status": "skipped_no_article",
                    }
                )
                continue

            geo_entities, region_tags = _extract_with_pipeline(pipeline, article)
            if geo_entities:
                extracted += 1
                _apply_event_geo(event, article, geo_entities, region_tags)
                _sync_event_geo_mappings(db, event, geo_entities)
                updated += 1
                details.append(
                    {
                        "event_id": event.id,
                        "title": event.title,
                        "status": "updated" if commit else "dry_run_updated",
                        "main_country": event.main_country,
                        "event_level": event.event_level,
                        "region_tags": region_tags,
                        "geo_keys": [entity.get("geo_key") for entity in geo_entities],
                    }
                )
            else:
                details.append(
                    {
                        "event_id": event.id,
                        "title": event.title,
                        "status": "no_geo_found",
                    }
                )

        if commit:
            db.commit()
        else:
            db.rollback()

        return {
            "mode": "commit" if commit else "dry_run",
            "scanned_events": scanned,
            "events_with_geo": extracted,
            "updated_events": updated,
            "skipped_events": skipped,
            "details": details,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--event-id")
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()

    result = run(limit=max(args.limit, 1), commit=args.commit, event_id=args.event_id)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=_json_default))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
