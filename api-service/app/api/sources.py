"""
Sources API endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import NewsSource

router = APIRouter()


@router.get("/", response_model=list)
async def get_sources(
    active_only: bool = True,
    db: Session = Depends(get_db),
):
    """Get all news sources."""
    query = db.query(NewsSource)

    if active_only:
        query = query.filter(NewsSource.is_active == True)

    sources = query.order_by(NewsSource.name).all()
    return sources


@router.get("/{source_id}")
async def get_source(
    source_id: str,
    db: Session = Depends(get_db),
):
    """Get a specific news source."""
    source = db.query(NewsSource).filter(NewsSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return source
