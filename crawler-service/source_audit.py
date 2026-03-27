#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

from scheduler import DEFAULT_SPIDERS

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://ainewser:ainewser_pass@localhost:5432/ainewser")
SPIDERS_ROOT = Path(__file__).resolve().parent / "news_crawler" / "spiders"


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def _find_spider_file(spider_name: str) -> str | None:
    matches = list(SPIDERS_ROOT.rglob(f"{spider_name}.py"))
    if not matches:
        return None
    return str(matches[0])


def _fetch_one(cur, query: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
    cur.execute(query, params)
    return cur.fetchone()


def main() -> int:
    now = datetime.now()
    since_24h = now - timedelta(hours=24)
    since_72h = now - timedelta(hours=72)

    conn = psycopg2.connect(DATABASE_URL)
    try:
        report: list[dict[str, Any]] = []
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            for config in DEFAULT_SPIDERS:
                source_row = _fetch_one(
                    cur,
                    """
                    SELECT id, name, code, base_url, country, language, category, is_active
                    FROM news_sources
                    WHERE code = %s
                    """,
                    (config.name,),
                )
                latest_job = _fetch_one(
                    cur,
                    """
                    SELECT id, status, started_at, finished_at, items_crawled, items_processed, error_message
                    FROM crawl_jobs
                    WHERE spider_name = %s
                    ORDER BY started_at DESC
                    LIMIT 1
                    """,
                    (config.name,),
                )
                article_stats = _fetch_one(
                    cur,
                    """
                    SELECT
                        COUNT(*) AS total_articles,
                        COUNT(*) FILTER (WHERE crawl_time >= %s) AS articles_24h,
                        COUNT(*) FILTER (WHERE crawl_time >= %s) AS articles_72h,
                        MAX(crawl_time) AS latest_article_time
                    FROM news_articles
                    WHERE source_code = %s
                    """,
                    (since_24h, since_72h, config.name),
                )

                spider_file = _find_spider_file(config.name)
                report.append(
                    {
                        "spider_name": config.name,
                        "priority": config.priority,
                        "interval_minutes": config.interval_minutes,
                        "configured_enabled": config.enabled,
                        "spider_file": spider_file,
                        "spider_file_exists": bool(spider_file),
                        "source_registered": bool(source_row),
                        "source": source_row,
                        "latest_job": latest_job,
                        "article_stats": article_stats,
                    }
                )

        summary = {
            "configured_spiders": len(DEFAULT_SPIDERS),
            "registered_sources": sum(1 for item in report if item["source_registered"]),
            "spider_files_present": sum(1 for item in report if item["spider_file_exists"]),
            "sources_with_articles_24h": sum(
                1
                for item in report
                if (item.get("article_stats") or {}).get("articles_24h")
            ),
            "sources_with_completed_recent_job": sum(
                1
                for item in report
                if (item.get("latest_job") or {}).get("status") == "completed"
            ),
        }

        print(json.dumps({"summary": summary, "sources": report}, ensure_ascii=False, indent=2, default=_json_default))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
