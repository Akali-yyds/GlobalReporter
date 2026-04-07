"""Video probe execution and health management."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import unescape
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from app.models import VideoJobCheckpoint, VideoJobProfile, VideoSource

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0 Safari/537.36"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _request_text(url: str, timeout: int = 20) -> tuple[int, str]:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", "ignore")
        return getattr(response, "status", 200), body


def _extract_meta(html: str, key: str) -> str | None:
    patterns = [
        rf'<meta[^>]+property=["\']{re.escape(key)}["\'][^>]+content=["\']([^"\']+)["\']',
        rf'<meta[^>]+name=["\']{re.escape(key)}["\'][^>]+content=["\']([^"\']+)["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return unescape(match.group(1)).strip()
    return None


def _get_or_create_checkpoint(db: Session, source_code: str, job_code: str) -> VideoJobCheckpoint:
    checkpoint = (
        db.query(VideoJobCheckpoint)
        .filter(
            VideoJobCheckpoint.source_code == source_code,
            VideoJobCheckpoint.job_code == job_code,
        )
        .first()
    )
    if checkpoint is None:
        checkpoint = VideoJobCheckpoint(source_code=source_code, job_code=job_code)
        db.add(checkpoint)
        db.flush()
    return checkpoint


def _apply_auto_downgrade(source: VideoSource, checkpoint: VideoJobCheckpoint) -> None:
    if checkpoint.consecutive_failures >= 6:
        source.rollout_state = "paused"
        source.enabled = False
        source.status = "error"
    elif checkpoint.consecutive_failures >= 3 and source.rollout_state == "default":
        source.rollout_state = "canary"
        source.status = "error"


def _mark_success(
    source: VideoSource,
    checkpoint: VideoJobCheckpoint,
    *,
    http_status: int,
    is_live: bool,
    title: str | None,
    thumbnail_url: str | None,
) -> dict:
    now = _now()
    checkpoint.last_probe_at = now
    checkpoint.last_success_at = now
    checkpoint.last_http_status = http_status
    checkpoint.last_error = None
    checkpoint.is_live = bool(is_live)
    checkpoint.last_title = title or checkpoint.last_title or source.title
    checkpoint.last_thumbnail = thumbnail_url or checkpoint.last_thumbnail or source.thumbnail_url
    checkpoint.consecutive_failures = 0

    source.status = "live" if is_live else "offline"
    source.title = checkpoint.last_title or source.title
    source.thumbnail_url = checkpoint.last_thumbnail or source.thumbnail_url

    return {
        "ok": True,
        "status": source.status,
        "is_live": bool(is_live),
        "http_status": http_status,
        "title": source.title,
        "thumbnail_url": source.thumbnail_url,
        "error": None,
    }


def _mark_failure(source: VideoSource, checkpoint: VideoJobCheckpoint, *, http_status: int | None, error: str) -> dict:
    now = _now()
    checkpoint.last_probe_at = now
    checkpoint.last_http_status = http_status
    checkpoint.last_error = error[:1000]
    checkpoint.is_live = False
    checkpoint.consecutive_failures = int(checkpoint.consecutive_failures or 0) + 1
    source.status = "error"
    _apply_auto_downgrade(source, checkpoint)
    return {
        "ok": False,
        "status": source.status,
        "is_live": False,
        "http_status": http_status,
        "title": checkpoint.last_title or source.title,
        "thumbnail_url": checkpoint.last_thumbnail or source.thumbnail_url,
        "error": checkpoint.last_error,
    }


def probe_youtube_embed(source: VideoSource) -> dict:
    http_status = None
    title = source.title
    thumbnail = source.thumbnail_url
    try:
        status, embed_html = _request_text(source.embed_url or "")
        http_status = status
        unavailable = "Video unavailable" in embed_html or "This video is unavailable" in embed_html

        channel_url = str((source.source_metadata or {}).get("channel_url") or "").strip()
        if channel_url:
            try:
                _, channel_html = _request_text(channel_url)
                title = _extract_meta(channel_html, "og:title") or title
                thumbnail = _extract_meta(channel_html, "og:image") or thumbnail
            except Exception:
                pass

        return {
            "http_status": http_status,
            "is_live": not unavailable,
            "title": title,
            "thumbnail_url": thumbnail,
            "error": None if not unavailable else "Embed returned unavailable state",
        }
    except HTTPError as exc:
        return {
            "http_status": exc.code,
            "is_live": False,
            "title": title,
            "thumbnail_url": thumbnail,
            "error": f"HTTP {exc.code}",
        }
    except URLError as exc:
        return {
            "http_status": http_status,
            "is_live": False,
            "title": title,
            "thumbnail_url": thumbnail,
            "error": str(exc.reason),
        }
    except Exception as exc:
        return {
            "http_status": http_status,
            "is_live": False,
            "title": title,
            "thumbnail_url": thumbnail,
            "error": str(exc),
        }


def probe_hls(source: VideoSource) -> dict:
    http_status = None
    try:
        request = Request(source.playback_url or "", headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=20) as response:
            http_status = getattr(response, "status", 200)
            payload = response.read(1024).decode("utf-8", "ignore")
        is_live = "#EXTM3U" in payload
        return {
            "http_status": http_status,
            "is_live": is_live,
            "title": source.title,
            "thumbnail_url": source.thumbnail_url,
            "error": None if is_live else "Playlist signature missing",
        }
    except HTTPError as exc:
        return {
            "http_status": exc.code,
            "is_live": False,
            "title": source.title,
            "thumbnail_url": source.thumbnail_url,
            "error": f"HTTP {exc.code}",
        }
    except URLError as exc:
        return {
            "http_status": http_status,
            "is_live": False,
            "title": source.title,
            "thumbnail_url": source.thumbnail_url,
            "error": str(exc.reason),
        }
    except Exception as exc:
        return {
            "http_status": http_status,
            "is_live": False,
            "title": source.title,
            "thumbnail_url": source.thumbnail_url,
            "error": str(exc),
        }


def probe_video_source(db: Session, source_code: str, job_code: str = "manual_probe") -> dict:
    source = db.query(VideoSource).filter(VideoSource.source_code == source_code).first()
    if source is None:
        raise ValueError(f"Video source not found: {source_code}")

    checkpoint = _get_or_create_checkpoint(db, source_code, job_code)
    result = probe_youtube_embed(source) if source.video_type == "youtube_embed" else probe_hls(source)

    if result["http_status"] and result["is_live"]:
        payload = _mark_success(
            source,
            checkpoint,
            http_status=result["http_status"],
            is_live=result["is_live"],
            title=result["title"],
            thumbnail_url=result["thumbnail_url"],
        )
    else:
        payload = _mark_failure(
            source,
            checkpoint,
            http_status=result["http_status"],
            error=result["error"] or "Probe failed",
        )

    db.commit()
    db.refresh(source)
    db.refresh(checkpoint)

    return {
        "ok": payload["ok"],
        "source_code": source.source_code,
        "job_code": job_code,
        "status": source.status,
        "is_live": checkpoint.is_live,
        "http_status": checkpoint.last_http_status,
        "title": checkpoint.last_title or source.title,
        "thumbnail_url": checkpoint.last_thumbnail or source.thumbnail_url,
        "error": checkpoint.last_error,
    }


def list_video_sources(
    db: Session,
    *,
    provider: str | None = None,
    video_type: str | None = None,
    rollout_state: str | None = None,
    region: str | None = None,
    topic: str | None = None,
) -> list[VideoSource]:
    query = db.query(VideoSource)
    if provider:
        query = query.filter(VideoSource.provider == provider)
    if video_type:
        query = query.filter(VideoSource.video_type == video_type)
    if rollout_state:
        query = query.filter(VideoSource.rollout_state == rollout_state)
    if region:
        query = query.filter(VideoSource.region == region)
    rows = query.order_by(VideoSource.priority.asc(), VideoSource.display_name.asc()).all()
    if topic:
        topic_lc = topic.strip().lower()
        rows = [row for row in rows if topic_lc in {str(tag).strip().lower() for tag in (row.topic_tags or [])}]
    return rows


def list_video_health(
    db: Session,
    *,
    provider: str | None = None,
    video_type: str | None = None,
    rollout_state: str | None = None,
    region: str | None = None,
    topic: str | None = None,
) -> list[tuple[VideoSource, VideoJobCheckpoint | None]]:
    sources = list_video_sources(
        db,
        provider=provider,
        video_type=video_type,
        rollout_state=rollout_state,
        region=region,
        topic=topic,
    )
    if not sources:
        return []
    by_code = {source.source_code: source for source in sources}
    checkpoints = (
        db.query(VideoJobCheckpoint)
        .filter(VideoJobCheckpoint.source_code.in_(list(by_code.keys())))
        .order_by(VideoJobCheckpoint.last_probe_at.desc())
        .all()
    )
    latest: dict[str, VideoJobCheckpoint] = {}
    for checkpoint in checkpoints:
        latest.setdefault(checkpoint.source_code, checkpoint)
    return [(source, latest.get(source.source_code)) for source in sources]


def run_due_video_probe_jobs(db: Session) -> list[dict]:
    now = _now()
    profiles = (
        db.query(VideoJobProfile)
        .filter(VideoJobProfile.enabled == True)
        .order_by(VideoJobProfile.interval_minutes.asc())
        .all()
    )
    results: list[dict] = []
    for profile in profiles:
        rollout_states = [profile.rollout_state]
        if profile.job_code == "video_probe_backfill":
            rollout_states = ["poc", "draft"]
        query = (
            db.query(VideoSource)
            .filter(
                VideoSource.enabled == True,
                VideoSource.rollout_state.in_(rollout_states),
            )
            .order_by(VideoSource.priority.asc(), VideoSource.display_name.asc())
        )
        sources = query.limit(profile.max_sources).all()
        for source in sources:
            checkpoint = _get_or_create_checkpoint(db, source.source_code, profile.job_code)
            if checkpoint.last_probe_at and checkpoint.last_probe_at > now - timedelta(minutes=profile.interval_minutes):
                continue
            results.append(probe_video_source(db, source.source_code, job_code=profile.job_code))
    return results
