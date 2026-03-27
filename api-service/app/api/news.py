"""
News API endpoints.
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models import NewsArticle, NewsEvent, EventArticle, EventGeoMapping, GeoEntity
from app.schemas.event import (
    NewsEventListItem,
    NewsEventResponse,
    EventGeoMappingResponse,
    RelatedSourceItem,
)
from app.schemas.news import NewsArticleResponse
from app.schemas.ingest import CrawledArticleIngest
from app.services.news_ingest import ingest_crawled_articles
from app.utils.ttl_cache import TTLCache

_hot_news_cache = TTLCache(ttl_seconds=20.0)

router = APIRouter()


@router.post("/ingest")
async def ingest_from_crawler(
    body: CrawledArticleIngest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Internal endpoint: Scrapy pipeline POSTs crawled rows here.
    Creates NewsSource/NewsArticle/NewsEvent so GET /api/news/hot returns data.
    """
    try:
        result = ingest_crawled_articles(db, [body.model_dump(by_alias=True)])
        return {"ok": True, **result}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/ingest/batch")
async def ingest_batch(
    items: List[CrawledArticleIngest],
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Batch ingest for crawlers."""
    try:
        result = ingest_crawled_articles(db, [i.model_dump(by_alias=True) for i in items])
        return {"ok": True, **result}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/hot")
async def get_hot_news(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    scope: Optional[str] = Query(None, pattern="^(all|china|world)$"),
    category: Optional[str] = None,
    level: Optional[str] = Query(None, pattern="^(country|city|region)$"),
    min_heat: Optional[int] = Query(None, ge=0),
    since_hours: Optional[int] = Query(None, ge=1, le=720),
    db: Session = Depends(get_db),
):
    """
    Get hot news events.
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20, max: 100)
    - scope: Filter by scope (all/china/world)
    - category: Filter by category
    - level: Filter by event_level (country/city/region)
    - min_heat: Minimum heat score threshold
    """
    query = db.query(NewsEvent)

    if scope == "china":
        query = query.filter(NewsEvent.main_country.in_(["CN", "TW", "HK"]))
    elif scope == "world":
        query = query.filter(~NewsEvent.main_country.in_(["CN", "TW", "HK", "UNKNOWN"]))

    if category:
        query = query.filter(NewsEvent.category == category)

    if level:
        query = query.filter(NewsEvent.event_level == level)

    if min_heat is not None:
        query = query.filter(NewsEvent.heat_score >= min_heat)

    if since_hours is not None:
        from datetime import datetime, timedelta, timezone
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=since_hours)
        query = query.filter(NewsEvent.last_seen_at >= cutoff)

    cache_key = f"hot:{scope}:{category}:{level}:{min_heat}:{since_hours}:{page}:{page_size}"
    hit, cached = _hot_news_cache.get(cache_key)
    if hit:
        return cached

    # Get total count
    total = query.count()

    # Apply pagination
    offset = (page - 1) * page_size
    events = query.order_by(desc(NewsEvent.heat_score)).offset(offset).limit(page_size).all()

    items = [NewsEventListItem.model_validate(e).model_dump() for e in events]

    result = {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }
    _hot_news_cache.set(cache_key, result)
    return result


@router.get("/events/{event_id}")
async def get_event_detail(
    event_id: str,
    db: Session = Depends(get_db),
):
    """Get detailed information about a news event."""
    event = db.query(NewsEvent).filter(NewsEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    mappings = db.query(EventGeoMapping).filter(EventGeoMapping.event_id == event_id).all()
    geo_by_id = {
        geo.id: geo
        for geo in db.query(GeoEntity).filter(GeoEntity.id.in_([m.geo_id for m in mappings if m.geo_id])).all()
    }
    geo_payload = []
    for mapping in mappings:
        geo = geo_by_id.get(mapping.geo_id)
        geo_type = None
        display_type = None
        geo_name = None
        if geo:
            precision_level = (geo.precision_level or "").upper()
            if precision_level == "ADMIN1":
                geo_type = "admin1"
            elif precision_level == "CITY":
                geo_type = "city"
            else:
                geo_type = "country"
            display_type = (geo.display_mode or "").lower() or ("point" if geo_type == "city" else "polygon")
            geo_name = geo.name

        geo_payload.append(
            EventGeoMappingResponse(
                id=mapping.id,
                event_id=mapping.event_id,
                geo_id=mapping.geo_id,
                geo_key=mapping.geo_key,
                confidence=float(mapping.confidence or 1.0),
                matched_text=mapping.matched_text,
                extraction_method=mapping.extraction_method,
                relevance_score=float(mapping.relevance_score) if mapping.relevance_score is not None else None,
                is_primary=bool(mapping.is_primary),
                source_text_position=mapping.source_text_position,
                geo_type=geo_type,
                display_type=display_type,
                geo_name=geo_name,
            ).model_dump()
        )

    payload = NewsEventResponse.model_validate(event).model_dump()
    payload["geo_mappings"] = geo_payload

    rows = (
        db.query(EventArticle, NewsArticle)
        .join(NewsArticle, EventArticle.article_id == NewsArticle.id)
        .filter(EventArticle.event_id == event_id)
        .order_by(desc(NewsArticle.heat_score), desc(NewsArticle.crawl_time))
        .all()
    )
    if rows:
        primary_art = rows[0][1]
        payload["primary_article_url"] = primary_art.article_url
        payload["primary_source_name"] = primary_art.source_name
        payload["primary_source_code"] = primary_art.source_code
        payload["primary_source_url"] = primary_art.source_url

        seen: set[tuple[str, str]] = set()
        related: List[RelatedSourceItem] = []
        for _ea, art in rows:
            key = (art.source_code or "", art.source_name or "")
            if key in seen:
                continue
            seen.add(key)
            related.append(
                RelatedSourceItem(
                    source_name=art.source_name or "Unknown",
                    source_code=art.source_code or "unknown",
                    article_url=art.article_url,
                )
            )
        payload["related_sources"] = [r.model_dump() for r in related]

    return payload


@router.get("/articles/{article_id}")
async def get_article_detail(
    article_id: str,
    db: Session = Depends(get_db),
):
    """Get detailed information about a news article."""
    article = db.query(NewsArticle).filter(NewsArticle.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return NewsArticleResponse.model_validate(article).model_dump()
