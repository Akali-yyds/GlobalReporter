"""
Persist crawled items via the same SQLAlchemy path as the API (no HTTP).

Avoids urllib blocking when the API process is busy or the HTTP handler stalls.
Set CRAWLER_HTTP_INGEST=1 to force HTTP-only ingestion.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_API_ROOT = _REPO_ROOT / "api-service"


def try_direct_ingest(payload: dict) -> bool:
    """
    Returns True if the row was written via the API service ingest function.
    Returns False if direct ingest is disabled or api-service is not importable.
    """
    v = os.environ.get("CRAWLER_HTTP_INGEST", "").strip().lower()
    if v in ("1", "true", "yes", "on"):
        return False
    if not (_API_ROOT / "app").is_dir():
        return False

    try:
        from dotenv import load_dotenv

        env = _REPO_ROOT / ".env"
        if env.is_file():
            load_dotenv(env)
    except Exception:
        pass

    api_path = str(_API_ROOT)
    if api_path not in sys.path:
        sys.path.insert(0, api_path)

    try:
        from app.database import SessionLocal
        from app.services.news_ingest import ingest_crawled_articles
    except Exception as e:
        logger.warning("[Ingest] Direct import failed (use HTTP or install api deps): %s", e)
        return False

    db = SessionLocal()
    try:
        ingest_crawled_articles(db, [payload])
    except Exception as e:
        db.rollback()
        logger.warning("[Ingest] Direct DB ingest failed: %s", e)
        return False
    finally:
        db.close()
    return True
