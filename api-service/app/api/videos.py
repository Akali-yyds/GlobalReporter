"""Video source API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import VideoSource
from app.schemas.video import (
    VideoHealthResponse,
    VideoProbeCheckpointResponse,
    VideoProbeResponse,
    VideoSourcePatchRequest,
    VideoSourceResponse,
    VideoSourceWithHealthResponse,
)
from app.services.video_probe_service import list_video_health, probe_video_source
from app.services.video_source_service import ensure_video_seed_data


router = APIRouter()


def _to_source_with_health(source: VideoSource, checkpoint) -> VideoSourceWithHealthResponse:
    return VideoSourceWithHealthResponse(
        **VideoSourceResponse.model_validate(source).model_dump(),
        checkpoint=VideoProbeCheckpointResponse.model_validate(checkpoint) if checkpoint else None,
    )


@router.get("/sources", response_model=list[VideoSourceWithHealthResponse])
async def get_video_sources(
    provider: str | None = None,
    video_type: str | None = Query(None, pattern="^(youtube_embed|hls)$"),
    rollout_state: str | None = Query(None, pattern="^(draft|poc|canary|default|paused)$"),
    region: str | None = None,
    topic: str | None = None,
    db: Session = Depends(get_db),
):
    ensure_video_seed_data(db)
    items = list_video_health(
        db,
        provider=provider,
        video_type=video_type,
        rollout_state=rollout_state,
        region=region,
        topic=topic,
    )
    return [_to_source_with_health(source, checkpoint) for source, checkpoint in items]


@router.get("/sources/{source_code}", response_model=VideoSourceWithHealthResponse)
async def get_video_source(source_code: str, db: Session = Depends(get_db)):
    ensure_video_seed_data(db)
    items = list_video_health(db)
    for source, checkpoint in items:
        if source.source_code == source_code:
            return _to_source_with_health(source, checkpoint)
    raise HTTPException(status_code=404, detail="Video source not found")


@router.get("/health", response_model=VideoHealthResponse)
async def get_video_health(
    provider: str | None = None,
    video_type: str | None = Query(None, pattern="^(youtube_embed|hls)$"),
    rollout_state: str | None = Query(None, pattern="^(draft|poc|canary|default|paused)$"),
    region: str | None = None,
    topic: str | None = None,
    db: Session = Depends(get_db),
):
    ensure_video_seed_data(db)
    items = list_video_health(
        db,
        provider=provider,
        video_type=video_type,
        rollout_state=rollout_state,
        region=region,
        topic=topic,
    )
    return VideoHealthResponse(
        sources=[_to_source_with_health(source, checkpoint) for source, checkpoint in items]
    )


@router.post("/probe/{source_code}", response_model=VideoProbeResponse)
async def probe_video(source_code: str, db: Session = Depends(get_db)):
    ensure_video_seed_data(db)
    try:
        return VideoProbeResponse(**probe_video_source(db, source_code, job_code="manual_probe"))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/sources/{source_code}", response_model=VideoSourceResponse)
async def patch_video_source(
    source_code: str,
    payload: VideoSourcePatchRequest,
    db: Session = Depends(get_db),
):
    ensure_video_seed_data(db)
    source = db.query(VideoSource).filter(VideoSource.source_code == source_code).first()
    if source is None:
        raise HTTPException(status_code=404, detail="Video source not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(source, key, value)
    db.commit()
    db.refresh(source)
    return source
