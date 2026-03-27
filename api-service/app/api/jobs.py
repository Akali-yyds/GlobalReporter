"""
Jobs API endpoints.
"""
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models import CrawlJob
from app.schemas.job import CrawlJobResponse, CrawlTriggerBody
from app.crawler_runner import trigger_crawl_once

router = APIRouter()


def _job_to_dict(job: CrawlJob) -> dict:
    return CrawlJobResponse.model_validate(job).model_dump()


@router.get("/latest")
async def get_latest_job(
    db: Session = Depends(get_db),
):
    """Get the latest crawl job."""
    job = db.query(CrawlJob).order_by(desc(CrawlJob.started_at)).first()

    if not job:
        return {"job": None}

    return {"job": _job_to_dict(job)}


@router.get("/")
async def get_jobs(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    """Get crawl job history."""
    offset = (page - 1) * page_size
    jobs = db.query(CrawlJob).order_by(desc(CrawlJob.started_at)).offset(offset).limit(page_size).all()
    total = db.query(CrawlJob).count()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_job_to_dict(j) for j in jobs],
    }


@router.post("/crawl")
async def run_crawl_now(
    body: CrawlTriggerBody = Body(default_factory=CrawlTriggerBody),
    spider: Optional[str] = Query(None, description="Legacy: spider name if JSON body omitted"),
):
    """
    Trigger a crawl in the background (manual refresh).

    - **JSON body** ``max_items`` (5–500): Scrapy ``-a max_items=`` + ``CLOSESPIDER_ITEMCOUNT``.
    - **crawl_scope** ``china`` | ``world`` | ``all``: run multiple spiders (新浪/腾讯 + BBC/Reuters/CNN).
    - Without ``crawl_scope``, runs one spider: ``body.spider``, query ``spider``, or ``CRAWLER_SPIDER``.
    """
    sp = body.spider or spider
    ok = trigger_crawl_once(
        spider_name=sp,
        max_items=body.max_items,
        crawl_scope=body.crawl_scope,
    )
    if not ok:
        raise HTTPException(
            status_code=503,
            detail="Crawler is already running; try again shortly.",
        )
    return {"status": "started", "message": "Crawl scheduled in background"}


@router.get("/{job_id}")
async def get_job(
    job_id: str,
    db: Session = Depends(get_db),
):
    """Get a specific crawl job."""
    job = db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_dict(job)
