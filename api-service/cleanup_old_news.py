"""
Database cleanup: remove news older than 3 days.
Safe to run as a scheduled task or manually.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Load .env
try:
    from dotenv import load_dotenv
    env = Path(__file__).resolve().parent.parent.parent / ".env"
    if env.is_file():
        load_dotenv(env)
except Exception:
    pass


def get_db_url() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:123321@localhost:5432/ainewser?client_encoding=UTF8",
    )


def cleanup(days: int = 3) -> dict:
    """Delete news events and articles older than `days` days."""
    try:
        from sqlalchemy import create_engine, text
        from sqlalchemy.orm import sessionmaker
    except ImportError as e:
        logger.error("sqlalchemy not installed: %s", e)
        return {"error": str(e)}

    url = get_db_url()
    engine = create_engine(url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    db = Session()

    cutoff = datetime.utcnow() - timedelta(days=days)
    cutoff_str = cutoff.isoformat()
    logger.info("Cleaning up records before %s (%d days)", cutoff_str, days)

    try:
        # Get event IDs to delete first (cascade to event_articles)
        result = db.execute(
            text("SELECT id FROM news_events WHERE last_seen_at < :cutoff"),
            {"cutoff": cutoff},
        )
        event_ids = [row[0] for row in result.fetchall()]
        event_count = len(event_ids)

        if event_ids:
            # Delete event_articles junction rows
            db.execute(
                text("DELETE FROM event_articles WHERE event_id = ANY(:ids)"),
                {"ids": event_ids},
            )
            logger.info("Deleted event_articles for %d events", event_count)

            # Delete geo mappings
            db.execute(
                text("DELETE FROM event_geo_mappings WHERE event_id = ANY(:ids)"),
                {"ids": event_ids},
            )
            logger.info("Deleted event_geo_mappings for %d events", event_count)

            # Delete the events
            db.execute(
                text("DELETE FROM news_events WHERE id = ANY(:ids)"),
                {"ids": event_ids},
            )
            logger.info("Deleted %d news_events", event_count)
        else:
            logger.info("No news_events to delete")
            event_count = 0

        # Delete orphaned articles (no longer linked to any event)
        result = db.execute(
            text("""
                SELECT a.id FROM news_articles a
                LEFT JOIN event_articles ea ON a.id = ea.article_id
                WHERE ea.article_id IS NULL
                AND a.crawl_time < :cutoff
            """),
            {"cutoff": cutoff},
        )
        orphan_ids = [row[0] for row in result.fetchall()]
        orphan_count = len(orphan_ids)

        if orphan_ids:
            db.execute(
                text("DELETE FROM news_articles WHERE id = ANY(:ids)"),
                {"ids": orphan_ids},
            )
            logger.info("Deleted %d orphaned news_articles", orphan_count)
        else:
            logger.info("No orphaned news_articles to delete")

        return {
            "events_deleted": event_count,
            "articles_deleted": orphan_count,
            "cutoff": cutoff_str,
            "days": days,
        }

    except Exception as e:
        logger.exception("Cleanup failed: %s", e)
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Clean up news older than N days (default: 3)")
    parser.add_argument(
        "--days", "-d", type=int, default=3,
        help="Delete records older than this many days (default: 3)",
    )
    args = parser.parse_args()
    result = cleanup(days=args.days)
    if "error" in result:
        logger.error("Cleanup failed: %s", result["error"])
        sys.exit(1)
    else:
        logger.info(
            "Cleanup complete: %d events, %d articles removed (before %s)",
            result["events_deleted"],
            result["articles_deleted"],
            result["cutoff"],
        )


if __name__ == "__main__":
    main()
