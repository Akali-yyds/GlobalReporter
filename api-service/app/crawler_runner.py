"""
Background Scrapy runner: periodic crawls + manual trigger.

Uses subprocess against the sibling `crawler-service` Scrapy project.
Set CRAWLER_PYTHON to a Python that has Scrapy installed if the API venv does not.
"""
from __future__ import annotations

import itertools
import logging
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# Used when crawl_scope is set (manual refresh from UI).
# Keep in sync with crawler-service/scheduler.py DEFAULT_SPIDERS.
CHINA_SPIDERS: List[str] = ["sina", "global_times", "tencent"]
WORLD_SPIDERS: List[str] = [
    "cnn", "guardian",                      # US/UK (ap feeds unreachable on some nets)
    "bbc",                                   # UK
    "aljazeera", "dw", "france24",          # International (reuters bot-blocked)
    "cna", "scmp", "nhk", "ndtv",           # Asia-Pacific
]

# Background rotation: alternates CN and World sources for broad coverage
_BACKGROUND_ROTATION: List[str] = [
    "bbc", "sina",
    "guardian", "tencent",
    "dw", "global_times",
    "bbc", "sina",
]
_bg_spider_cycle = itertools.cycle(_BACKGROUND_ROTATION)

_runner_lock = threading.Lock()
_bg_thread: Optional[threading.Thread] = None
_stop_flag = threading.Event()


def _project_root() -> Path:
    # api-service/app/crawler_runner.py -> api-service -> repo root
    return Path(__file__).resolve().parent.parent.parent


def _crawler_cwd() -> Path:
    return _project_root() / "crawler-service"


def _python_executable() -> str:
    return os.environ.get("CRAWLER_PYTHON", sys.executable)


def _clamp_max_items(n: int) -> int:
    return max(5, min(500, int(n)))


def _run_scrapy_sync(spider_name: str, max_items: int = 50) -> int:
    """Run `scrapy crawl <spider>` synchronously. Returns process return code."""
    cwd = _crawler_cwd()
    if not cwd.is_dir():
        logger.error("Crawler project not found at %s", cwd)
        return 127

    mi = _clamp_max_items(max_items)

    env = os.environ.copy()
    env.setdefault("SCRAPY_SETTINGS_MODULE", "news_crawler.settings")
    env.setdefault("API_BASE_URL", os.environ.get("API_BASE_URL", "http://127.0.0.1:8000"))
    # Ensure the crawler-service directory is in PYTHONPATH so news_crawler is importable
    python_path = env.get("PYTHONPATH", "")
    crawler_path = str(cwd)
    if python_path:
        env["PYTHONPATH"] = f"{crawler_path}{os.pathsep}{python_path}"
    else:
        env["PYTHONPATH"] = crawler_path

    cmd = [
        _python_executable(),
        "-m",
        "scrapy",
        "crawl",
        spider_name,
        "-a",
        f"max_items={mi}",
        "-s",
        f"CLOSESPIDER_ITEMCOUNT={mi}",
    ]

    t_start = time.monotonic()
    logger.info("Running crawler: %s (cwd=%s)", " ".join(cmd), cwd)
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
        )
    except FileNotFoundError:
        logger.exception("Python executable not found: %s", _python_executable())
        return 127
    except subprocess.TimeoutExpired:
        logger.error("Crawler timed out for spider=%s", spider_name)
        return 124

    elapsed = time.monotonic() - t_start
    err = proc.stderr or ""

    # Extract key Scrapy stats from stderr
    m_scraped = re.search(r"'item_scraped_count':\s*(\d+)", err)
    m_dropped = re.search(r"'item_dropped_count':\s*(\d+)", err)
    scraped = int(m_scraped.group(1)) if m_scraped else None
    dropped = int(m_dropped.group(1)) if m_dropped else 0

    if proc.returncode != 0:
        logger.warning(
            "Crawler FAILED spider=%s rc=%s elapsed=%.1fs | STDERR tail: %s",
            spider_name,
            proc.returncode,
            elapsed,
            err[-4000:] if err else "(empty)",
        )
    else:
        if scraped is not None:
            logger.info(
                "Crawler OK spider=%s scraped=%s dropped=%s elapsed=%.1fs",
                spider_name, scraped, dropped, elapsed,
            )
        else:
            logger.info("Crawler OK spider=%s elapsed=%.1fs", spider_name, elapsed)
        if scraped == 0:
            logger.warning(
                "Spider %s returned 0 items (%.1fs). STDERR tail:\n%s",
                spider_name, elapsed, err[-4000:] if err else "(empty)",
            )

    return proc.returncode


def _run_scrapy_with_retry(spider_name: str, max_items: int = 50, max_retries: int = 1) -> int:
    """Run a spider with one automatic retry on transient failure (rc != 0 and rc != 127)."""
    rc = _run_scrapy_sync(spider_name, max_items)
    if rc not in (0, 127, 124) and max_retries > 0:
        logger.warning("Retrying spider=%s after rc=%s", spider_name, rc)
        time.sleep(5)
        rc = _run_scrapy_sync(spider_name, max_items)
        if rc != 0:
            logger.error("Spider %s still failed after retry: rc=%s", spider_name, rc)
    return rc


def _spiders_for_scope(crawl_scope: str) -> List[str]:
    s = (crawl_scope or "").lower().strip()
    if s == "china":
        return list(CHINA_SPIDERS)
    if s == "world":
        return list(WORLD_SPIDERS)
    if s == "all":
        return list(CHINA_SPIDERS) + list(WORLD_SPIDERS)
    return []


def trigger_crawl_once(
    spider_name: Optional[str] = None,
    max_items: int = 50,
    crawl_scope: Optional[str] = None,
) -> bool:
    """
    Start a crawl in a daemon thread (non-blocking). Returns False if already running
    or crawler path missing.

    If ``crawl_scope`` is ``china`` / ``world`` / ``all``, runs multiple spiders
    sequentially with a per-spider item budget derived from ``max_items``.
    Otherwise runs a single spider (``spider_name`` or ``CRAWLER_SPIDER``).
    """
    from app.config import settings

    cwd = _crawler_cwd()
    if not cwd.is_dir():
        return False

    if not _runner_lock.acquire(blocking=False):
        logger.info("Crawler run skipped: another run is active")
        return False

    scope_list = _spiders_for_scope(crawl_scope) if crawl_scope else []
    single_name = spider_name or settings.CRAWLER_SPIDER
    total_budget = _clamp_max_items(max_items)

    def _work():
        try:
            if scope_list:
                n = len(scope_list)
                per = max(1, total_budget // n)
                # Distribute remainder to first spiders
                rem = total_budget - per * n
                for i, sp in enumerate(scope_list):
                    budget = per + (1 if i < rem else 0)
                    logger.info(
                        "Crawl scope=%s spider=%s/%s max_items=%s",
                        crawl_scope,
                        sp,
                        i + 1,
                        budget,
                    )
                    _run_scrapy_with_retry(sp, budget)
            else:
                _run_scrapy_with_retry(single_name, total_budget)
        finally:
            _runner_lock.release()

    t = threading.Thread(target=_work, name="crawler-once", daemon=True)
    t.start()
    return True


def _background_loop():
    from app.config import settings

    interval = max(60, int(settings.CRAWLER_INTERVAL_SECONDS))
    spider = settings.CRAWLER_SPIDER

    logger.info(
        "Crawler background loop started: spider=%s interval=%ss",
        spider,
        interval,
    )

    # Initial run shortly after API startup
    time.sleep(5)
    while not _stop_flag.is_set():
        if _runner_lock.acquire(blocking=False):
            try:
                next_spider = next(_bg_spider_cycle)
                logger.info("Background crawl tick: spider=%s", next_spider)
                _run_scrapy_with_retry(next_spider, max_items=50)
            finally:
                _runner_lock.release()
        else:
            logger.debug("Skipping scheduled crawl: manual run in progress")

        if _stop_flag.wait(timeout=interval):
            break

    logger.info("Crawler background loop stopped")


def start_background_crawler() -> None:
    from app.config import settings

    if not getattr(settings, "CRAWLER_ENABLED", False):
        logger.info("CRAWLER_ENABLED is false — background crawler not started")
        return

    if not _crawler_cwd().is_dir():
        logger.warning("crawler-service directory missing — background crawler not started")
        return

    global _bg_thread
    _stop_flag.clear()
    _bg_thread = threading.Thread(target=_background_loop, name="crawler-bg", daemon=True)
    _bg_thread.start()


def stop_background_crawler() -> None:
    _stop_flag.set()
    if _bg_thread and _bg_thread.is_alive():
        _bg_thread.join(timeout=5)
