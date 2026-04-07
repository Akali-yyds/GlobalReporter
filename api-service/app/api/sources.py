"""
Sources API endpoints.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    CrawlJob,
    EventArticle,
    NewsArticle,
    NewsEvent,
    NewsSource,
    SourceFeedHealth,
    SourceFeedProfile,
    SourcePolicy,
)
from app.schemas.source import (
    NewsSourceResponse,
    SourceAnalyticsItem,
    SourceAnalyticsResponse,
    SourceFeedHealthItem,
    SourceFeedProfilePatchRequest,
    SourceFeedProfileResponse,
    SourceFeedPromoteRequest,
    SourcePolicyResponse,
    SourceTierAnalyticsItem,
)

router = APIRouter()

_LOW_SIGNAL_CATEGORIES = {"social", "news", "general", "misc", "community"}
_ALWAYS_NOISY_CATEGORIES = {"entertainment", "celebrity", "variety"}
_FINE_GRAIN_EVENT_LEVELS = {"admin1", "admin2", "city", "district", "point"}
_ROLLOUT_STATES = ("draft", "poc", "canary", "default", "paused")
_PROMOTION_CHAIN = {
    "draft": "poc",
    "poc": "canary",
    "canary": "default",
    "default": "default",
    "paused": "canary",
}


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _latest_article_time(article: NewsArticle) -> datetime | None:
    return article.publish_time or article.crawl_time


def _validate_rollout_state(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized not in _ROLLOUT_STATES:
        raise HTTPException(status_code=400, detail=f"Invalid rollout_state: {value}")
    return normalized


def _has_geo(article: NewsArticle) -> bool:
    return bool(article.country_tags or article.region_tags or article.city_tags)


def _is_low_signal_article(article: NewsArticle) -> bool:
    tags = [str(tag).strip().lower() for tag in (article.tags or []) if str(tag).strip()]
    category = (article.category or "").strip().lower()
    title = (article.title or "").strip()

    if category in _ALWAYS_NOISY_CATEGORIES:
        return True
    if not tags and category in _LOW_SIGNAL_CATEGORIES:
        return True
    if len(title) < 12 and len(tags) <= 1 and category in _LOW_SIGNAL_CATEGORIES:
        return True
    return False


@router.get("/", response_model=list[NewsSourceResponse])
async def get_sources(
    active_only: bool = True,
    tier: str | None = None,
    db: Session = Depends(get_db),
):
    """Get all news sources."""
    query = db.query(NewsSource)

    if active_only:
        query = query.filter(NewsSource.is_active == True)
    if tier:
        query = query.filter(NewsSource.source_tier == tier)

    sources = query.order_by(NewsSource.name).all()
    return sources


@router.get("/policies", response_model=list[SourcePolicyResponse])
async def get_source_policies(
    source_class: str | None = Query(None, pattern="^(news|lead|event)$"),
    enabled_only: bool = False,
    db: Session = Depends(get_db),
):
    query = db.query(SourcePolicy)
    if source_class:
        query = query.filter(SourcePolicy.source_class == source_class)
    if enabled_only:
        query = query.filter(SourcePolicy.enabled == True)
    return query.order_by(SourcePolicy.source_code).all()


@router.get("/feeds", response_model=list[SourceFeedProfileResponse])
async def get_source_feeds(
    source_code: str | None = None,
    rollout_state: str | None = Query(None, pattern="^(draft|poc|canary|default|paused)$"),
    enabled_only: bool = False,
    db: Session = Depends(get_db),
):
    query = db.query(SourceFeedProfile)
    if source_code:
        query = query.filter(SourceFeedProfile.source_code == source_code)
    if rollout_state:
        query = query.filter(SourceFeedProfile.rollout_state == rollout_state)
    if enabled_only:
        query = query.filter(SourceFeedProfile.enabled == True)
    return query.order_by(
        SourceFeedProfile.source_code,
        SourceFeedProfile.priority.asc(),
        SourceFeedProfile.feed_name.asc(),
    ).all()


@router.get("/feeds/health", response_model=list[SourceFeedHealthItem])
async def get_source_feed_health(
    source_code: str | None = None,
    rollout_state: str | None = Query(None, pattern="^(draft|poc|canary|default|paused)$"),
    enabled_only: bool = False,
    db: Session = Depends(get_db),
):
    query = (
        db.query(SourceFeedProfile, SourceFeedHealth)
        .outerjoin(
            SourceFeedHealth,
            (SourceFeedHealth.source_code == SourceFeedProfile.source_code)
            & (SourceFeedHealth.feed_code == SourceFeedProfile.feed_code),
        )
    )
    if source_code:
        query = query.filter(SourceFeedProfile.source_code == source_code)
    if rollout_state:
        query = query.filter(SourceFeedProfile.rollout_state == rollout_state)
    if enabled_only:
        query = query.filter(SourceFeedProfile.enabled == True)

    rows = query.order_by(
        SourceFeedProfile.source_code,
        SourceFeedProfile.priority.asc(),
        SourceFeedProfile.feed_name.asc(),
    ).all()
    items: list[SourceFeedHealthItem] = []
    for feed, health in rows:
        items.append(
            SourceFeedHealthItem(
                feed_profile_id=feed.id,
                source_code=feed.source_code,
                feed_code=feed.feed_code,
                feed_name=feed.feed_name,
                feed_url=feed.feed_url,
                priority=feed.priority,
                freshness_sla_hours=feed.freshness_sla_hours,
                rollout_state=feed.rollout_state,
                enabled=bool(feed.enabled),
                expected_update_interval_hours=feed.expected_update_interval_hours,
                license_mode=feed.license_mode,
                last_fetch_at=health.last_fetch_at if health else None,
                last_success_at=health.last_success_at if health else None,
                last_fresh_item_at=health.last_fresh_item_at if health else None,
                last_http_status=health.last_http_status if health else None,
                last_error=health.last_error if health else None,
                scraped_count_24h=int(health.scraped_count_24h or 0) if health else 0,
                dropped_stale_count_24h=int(health.dropped_stale_count_24h or 0) if health else 0,
                dropped_quality_count_24h=int(health.dropped_quality_count_24h or 0) if health else 0,
                stale_ratio_24h=float(health.stale_ratio_24h or 0.0) if health else 0.0,
                direct_ok_rate_24h=float(health.direct_ok_rate_24h or 0.0) if health else 0.0,
                consecutive_failures=int(health.consecutive_failures or 0) if health else 0,
            )
        )
    return items


@router.patch("/feeds/{feed_id}", response_model=SourceFeedProfileResponse)
async def patch_source_feed(
    feed_id: str,
    payload: SourceFeedProfilePatchRequest,
    db: Session = Depends(get_db),
):
    feed = db.query(SourceFeedProfile).filter(SourceFeedProfile.id == feed_id).first()
    if feed is None:
        raise HTTPException(status_code=404, detail="Feed profile not found")

    data = payload.model_dump(exclude_unset=True)
    if "rollout_state" in data:
        data["rollout_state"] = _validate_rollout_state(data["rollout_state"])

    for key, value in data.items():
        setattr(feed, key, value)
    db.commit()
    db.refresh(feed)
    return feed


@router.post("/feeds/{feed_id}/promote", response_model=SourceFeedProfileResponse)
async def promote_source_feed(
    feed_id: str,
    payload: SourceFeedPromoteRequest,
    db: Session = Depends(get_db),
):
    feed = db.query(SourceFeedProfile).filter(SourceFeedProfile.id == feed_id).first()
    if feed is None:
        raise HTTPException(status_code=404, detail="Feed profile not found")

    target_state = _validate_rollout_state(payload.target_state) if payload.target_state else _PROMOTION_CHAIN.get(feed.rollout_state, "default")
    if target_state == "paused":
        raise HTTPException(status_code=400, detail="Use /pause to pause a feed")

    feed.rollout_state = target_state
    feed.enabled = target_state != "draft"
    db.commit()
    db.refresh(feed)
    return feed


@router.post("/feeds/{feed_id}/pause", response_model=SourceFeedProfileResponse)
async def pause_source_feed(
    feed_id: str,
    db: Session = Depends(get_db),
):
    feed = db.query(SourceFeedProfile).filter(SourceFeedProfile.id == feed_id).first()
    if feed is None:
        raise HTTPException(status_code=404, detail="Feed profile not found")

    feed.rollout_state = "paused"
    feed.enabled = False
    db.commit()
    db.refresh(feed)
    return feed


@router.get("/analytics", response_model=SourceAnalyticsResponse)
async def get_source_analytics(
    since_hours: int | None = Query(72, ge=1, le=720),
    freshness_hours: int = Query(24, ge=1, le=168),
    tier: str | None = Query(None, pattern="^(official|authoritative|aggregator|community|social)$"),
    active_only: bool = True,
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = None
    if since_hours is not None:
        cutoff = now - timedelta(hours=since_hours)
    freshness_cutoff = now - timedelta(hours=freshness_hours)

    source_query = db.query(NewsSource)
    if active_only:
        source_query = source_query.filter(NewsSource.is_active == True)
    if tier:
        source_query = source_query.filter(NewsSource.source_tier == tier)
    sources = source_query.order_by(NewsSource.name).all()

    source_items: list[SourceAnalyticsItem] = []
    tier_bucket: dict[str, dict] = {}

    for source in sources:
        article_query = db.query(NewsArticle).filter(NewsArticle.source_id == source.id)
        if cutoff is not None:
            article_query = article_query.filter(
                (NewsArticle.publish_time >= cutoff) | (NewsArticle.crawl_time >= cutoff)
            )
        articles = article_query.all()
        article_ids = [article.id for article in articles]

        event_query = (
            db.query(NewsEvent)
            .join(EventArticle, EventArticle.event_id == NewsEvent.id)
            .join(NewsArticle, NewsArticle.id == EventArticle.article_id)
            .filter(NewsArticle.source_id == source.id)
        )
        if cutoff is not None:
            event_query = event_query.filter(NewsEvent.last_seen_at >= cutoff)
        event_rows = event_query.all()
        deduped_events = {}
        for event in event_rows:
            deduped_events[event.id] = event
        events = list(deduped_events.values())
        job_query = db.query(CrawlJob).filter(CrawlJob.spider_name == source.code)
        if cutoff is not None:
            job_query = job_query.filter(CrawlJob.started_at >= cutoff)
        jobs = job_query.order_by(CrawlJob.started_at.desc()).all()

        article_count = len(articles)
        publish_time_covered = sum(1 for article in articles if article.publish_time is not None)
        fresh_articles = sum(
            1 for article in articles if (_latest_article_time(article) is not None and _latest_article_time(article) >= freshness_cutoff)
        )
        tag_covered = sum(1 for article in articles if article.tags)
        low_signal_articles = sum(1 for article in articles if _is_low_signal_article(article))
        geo_covered = sum(1 for article in articles if _has_geo(article))
        latest_publish_at = max((article.publish_time for article in articles if article.publish_time is not None), default=None)
        region_yield_events = sum(1 for event in events if (event.event_level or "").strip().lower() in _FINE_GRAIN_EVENT_LEVELS)
        recent_job_count = len(jobs)
        successful_job_count = sum(1 for job in jobs if (job.status or "").strip().lower() == "completed")
        last_job = jobs[0] if jobs else None
        last_success = next((job for job in jobs if (job.status or "").strip().lower() == "completed"), None)
        avg_heat = round(sum(int(event.heat_score or 0) for event in events) / len(events), 2) if events else 0.0
        latest_event_at = max((event.last_seen_at for event in events if event.last_seen_at is not None), default=None)
        source_items.append(
            SourceAnalyticsItem(
                code=source.code,
                name=source.name,
                source_class=source.source_class,
                source_tier=source.source_tier,
                source_tier_level=source.source_tier_level,
                freshness_sla_hours=source.freshness_sla_hours,
                license_mode=source.license_mode,
                is_active=bool(source.is_active),
                article_count=article_count,
                event_count=len(events),
                recent_job_count=recent_job_count,
                successful_job_count=successful_job_count,
                success_rate=_ratio(successful_job_count, recent_job_count),
                avg_event_heat=avg_heat,
                publish_time_coverage=_ratio(publish_time_covered, article_count),
                fresh_article_ratio=_ratio(fresh_articles, article_count),
                tag_coverage_ratio=_ratio(tag_covered, article_count),
                low_signal_ratio=_ratio(low_signal_articles, article_count),
                geo_coverage_ratio=_ratio(geo_covered, article_count),
                region_yield_ratio=_ratio(region_yield_events, len(events)),
                last_job_status=last_job.status if last_job else None,
                last_job_started_at=last_job.started_at if last_job else None,
                last_success_at=last_success.started_at if last_success else None,
                last_error_message=last_job.error_message if last_job and last_job.status != "completed" else None,
                latest_publish_at=latest_publish_at,
                latest_event_at=latest_event_at,
            )
        )

        bucket = tier_bucket.setdefault(
            source.source_tier,
            {
                "source_tier": source.source_tier,
                "source_count": 0,
                "active_source_count": 0,
                "article_count": 0,
                "event_count": 0,
                "recent_job_count": 0,
                "successful_job_count": 0,
                "heat_sum": 0.0,
                "heat_samples": 0,
                "publish_time_covered": 0,
                "fresh_articles": 0,
                "tag_covered": 0,
                "low_signal_articles": 0,
                "geo_covered": 0,
                "region_yield_events": 0,
                "last_job_started_at": None,
                "last_success_at": None,
                "latest_publish_at": None,
                "latest_event_at": None,
            },
        )
        bucket["source_count"] += 1
        if source.is_active:
            bucket["active_source_count"] += 1
        bucket["article_count"] += article_count
        bucket["event_count"] += len(events)
        bucket["recent_job_count"] += recent_job_count
        bucket["successful_job_count"] += successful_job_count
        bucket["publish_time_covered"] += publish_time_covered
        bucket["fresh_articles"] += fresh_articles
        bucket["tag_covered"] += tag_covered
        bucket["low_signal_articles"] += low_signal_articles
        bucket["geo_covered"] += geo_covered
        bucket["region_yield_events"] += region_yield_events
        if events:
            bucket["heat_sum"] += sum(int(event.heat_score or 0) for event in events)
            bucket["heat_samples"] += len(events)
        if last_job and (bucket["last_job_started_at"] is None or last_job.started_at > bucket["last_job_started_at"]):
            bucket["last_job_started_at"] = last_job.started_at
        if last_success and (bucket["last_success_at"] is None or last_success.started_at > bucket["last_success_at"]):
            bucket["last_success_at"] = last_success.started_at
        if latest_publish_at and (bucket["latest_publish_at"] is None or latest_publish_at > bucket["latest_publish_at"]):
            bucket["latest_publish_at"] = latest_publish_at
        if latest_event_at and (bucket["latest_event_at"] is None or latest_event_at > bucket["latest_event_at"]):
            bucket["latest_event_at"] = latest_event_at

    tier_items = [
        SourceTierAnalyticsItem(
            source_tier=bucket["source_tier"],
            source_count=bucket["source_count"],
            active_source_count=bucket["active_source_count"],
            article_count=bucket["article_count"],
            event_count=bucket["event_count"],
            recent_job_count=bucket["recent_job_count"],
            successful_job_count=bucket["successful_job_count"],
            success_rate=_ratio(bucket["successful_job_count"], bucket["recent_job_count"]),
            avg_event_heat=round(bucket["heat_sum"] / bucket["heat_samples"], 2) if bucket["heat_samples"] else 0.0,
            publish_time_coverage=_ratio(bucket["publish_time_covered"], bucket["article_count"]),
            fresh_article_ratio=_ratio(bucket["fresh_articles"], bucket["article_count"]),
            tag_coverage_ratio=_ratio(bucket["tag_covered"], bucket["article_count"]),
            low_signal_ratio=_ratio(bucket["low_signal_articles"], bucket["article_count"]),
            geo_coverage_ratio=_ratio(bucket["geo_covered"], bucket["article_count"]),
            region_yield_ratio=_ratio(bucket["region_yield_events"], bucket["event_count"]),
            last_job_started_at=bucket["last_job_started_at"],
            last_success_at=bucket["last_success_at"],
            latest_publish_at=bucket["latest_publish_at"],
            latest_event_at=bucket["latest_event_at"],
        )
        for bucket in sorted(tier_bucket.values(), key=lambda item: (-item["event_count"], item["source_tier"]))
    ]

    source_items.sort(
        key=lambda item: (
            -item.event_count,
            -(item.article_count or 0),
            item.name.lower(),
        )
    )
    return SourceAnalyticsResponse(
        since_hours=since_hours,
        freshness_hours=freshness_hours,
        tiers=tier_items,
        sources=source_items,
    )


@router.get("/{source_id}", response_model=NewsSourceResponse)
async def get_source(
    source_id: str,
    db: Session = Depends(get_db),
):
    """Get a specific news source."""
    source = db.query(NewsSource).filter(NewsSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source
