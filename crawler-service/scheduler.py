"""
Crawler scheduler script.
Schedules and runs spider crawls based on configuration.
"""
import argparse
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from uuid import uuid4

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / '.env')
import os
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://ainewser:ainewser_pass@localhost:5432/ainewser')


@dataclass
class SpiderConfig:
    """Configuration for a spider."""
    name: str
    enabled: bool = True
    interval_minutes: int = 60
    max_items: int = 10
    priority: int = 0


@dataclass
class CrawlJob:
    """Represents a crawl job."""
    source_id: str
    spider_name: str
    id: Optional[str] = None
    status: str = 'pending'
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    items_crawled: int = 0
    items_processed: int = 0
    error_message: Optional[str] = None


# Default spider configurations
DEFAULT_SPIDERS: List[SpiderConfig] = [
    # --- China (CN) ---
    SpiderConfig(name='sina',      interval_minutes=30, priority=10),
    SpiderConfig(name='global_times', interval_minutes=60, priority=7),
    SpiderConfig(name='tencent',   interval_minutes=30, priority=10),
    SpiderConfig(name='bilibili_hot', interval_minutes=45, priority=7),
    # --- US ---
    SpiderConfig(name='cnn',       interval_minutes=60, priority=7),
    SpiderConfig(name='ap',        interval_minutes=60, priority=7),
    # --- UK ---
    SpiderConfig(name='bbc',       interval_minutes=60, priority=7),
    SpiderConfig(name='guardian',  interval_minutes=60, priority=6),
    # --- International ---
    SpiderConfig(name='reuters',   interval_minutes=60, priority=8),
    SpiderConfig(name='aljazeera', interval_minutes=60, priority=6),
    SpiderConfig(name='dw',        interval_minutes=90, priority=5),
    SpiderConfig(name='france24',  interval_minutes=90, priority=5),
    # --- Asia-Pacific ---
    SpiderConfig(name='cna',       interval_minutes=60, priority=6),
    SpiderConfig(name='scmp',      interval_minutes=60, priority=6),
    SpiderConfig(name='nhk',       interval_minutes=90, priority=5),
    SpiderConfig(name='ndtv',      interval_minutes=90, priority=5),
    # --- Official / Community ---
    SpiderConfig(name='nasa_official', interval_minutes=120, priority=7),
    SpiderConfig(name='openai_official', interval_minutes=90, priority=8),
    SpiderConfig(name='google_blog', interval_minutes=90, priority=7),
    SpiderConfig(name='github_changelog', interval_minutes=60, priority=8),
    SpiderConfig(name='github_openai_releases', interval_minutes=120, priority=7),
    SpiderConfig(name='youtube_official', interval_minutes=60, priority=7),
]


class CrawlerScheduler:
    """Scheduler for managing crawler jobs."""

    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or DATABASE_URL
        self.spider_configs: Dict[str, SpiderConfig] = {
            s.name: s for s in DEFAULT_SPIDERS
        }
        self._conn = None

    @property
    def conn(self):
        """Get database connection."""
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(self.database_url)
        return self._conn

    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def get_source_id(self, spider_name: str) -> Optional[str]:
        """Get source ID by spider name."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id FROM news_sources WHERE code = %s",
                (spider_name,)
            )
            result = cur.fetchone()
            return result['id'] if result else None

    def get_last_job_time(self, spider_name: str) -> Optional[datetime]:
        """Get the last job completion time for a spider."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT started_at FROM crawl_jobs 
                WHERE spider_name = %s AND status = 'completed'
                ORDER BY started_at DESC LIMIT 1
                """,
                (spider_name,)
            )
            result = cur.fetchone()
            return result['started_at'] if result else None

    def create_job(self, spider_name: str) -> Optional[CrawlJob]:
        """Create a new crawl job."""
        source_id = self.get_source_id(spider_name)
        if not source_id:
            logger.warning(f"No source found for spider: {spider_name}")
            return None

        job = CrawlJob(
            source_id=source_id,
            spider_name=spider_name,
            status='pending',
            started_at=datetime.now()
        )

        job_id = str(uuid4())
        now = datetime.now()
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO crawl_jobs (id, source_id, spider_name, status, started_at, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (job_id, job.source_id, job.spider_name, job.status, job.started_at, now, now)
            )
            self.conn.commit()

        job.id = job_id
        logger.info(f"Created crawl job {job_id} for spider: {spider_name}")
        return job

    def update_job_status(
        self,
        job_id: str,
        status: str,
        items_crawled: int = 0,
        items_processed: int = 0,
        error_message: Optional[str] = None
    ):
        """Update job status."""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE crawl_jobs 
                SET status = %s, 
                    items_crawled = %s, 
                    items_processed = %s,
                    error_message = %s,
                    finished_at = %s,
                    updated_at = %s
                WHERE id = %s
                """,
                (status, items_crawled, items_processed, error_message, datetime.now(), datetime.now(), job_id)
            )
            self.conn.commit()

    def should_run(self, spider_name: str) -> bool:
        """Check if spider should run based on interval."""
        if spider_name not in self.spider_configs:
            return False

        config = self.spider_configs[spider_name]
        if not config.enabled:
            return False

        last_run = self.get_last_job_time(spider_name)
        if not last_run:
            return True

        # Check if enough time has passed
        elapsed = datetime.now() - last_run
        return elapsed >= timedelta(minutes=config.interval_minutes)

    def get_spiders_to_run(self) -> List[str]:
        """Get list of spiders that should run."""
        return [
            name for name in self.spider_configs
            if self.should_run(name)
        ]

    def run_spider(self, spider_name: str) -> bool:
        """Run a single spider."""
        logger.info(f"Starting spider: {spider_name}")

        # Create job
        job = self.create_job(spider_name)
        if not job:
            return False

        try:
            # Import scrapy and run spider
            import subprocess
            
            result = subprocess.run(
                ['scrapy', 'crawl', spider_name, '-s', f'CLOSESPIDER_ITEMCOUNT={self.spider_configs[spider_name].max_items}'],
                cwd='.',
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if result.returncode == 0:
                self.update_job_status(
                    job.id,
                    'completed',
                    items_crawled=result.stdout.count('Scraped'),
                    items_processed=result.stdout.count('Processed')
                )
                logger.info(f"Spider {spider_name} completed successfully")
                return True
            else:
                self.update_job_status(
                    job.id,
                    'failed',
                    error_message=result.stderr[:500]
                )
                logger.error(f"Spider {spider_name} failed: {result.stderr[:200]}")
                return False

        except subprocess.TimeoutExpired:
            self.update_job_status(
                job.id,
                'failed',
                error_message='Spider timed out after 5 minutes'
            )
            logger.error(f"Spider {spider_name} timed out")
            return False
        except Exception as e:
            self.update_job_status(
                job.id,
                'failed',
                error_message=str(e)[:500]
            )
            logger.error(f"Spider {spider_name} error: {e}")
            return False

    def run_all(self):
        """Run all due spiders."""
        spiders = self.get_spiders_to_run()
        if not spiders:
            logger.info("No spiders due to run")
            return

        logger.info(f"Running {len(spiders)} spiders: {spiders}")

        # Sort by priority (higher first)
        spiders.sort(key=lambda s: self.spider_configs[s].priority, reverse=True)

        success_count = 0
        for spider in spiders:
            if self.run_spider(spider):
                success_count += 1
            time.sleep(5)  # Delay between spiders

        logger.info(f"Completed {success_count}/{len(spiders)} spiders successfully")

    def run_daemon(self, check_interval: int = 60):
        """Run scheduler as a daemon."""
        logger.info(f"Starting scheduler daemon (check interval: {check_interval}s)")
        
        try:
            while True:
                self.run_all()
                time.sleep(check_interval)
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
        finally:
            self.close()


def main():
    parser = argparse.ArgumentParser(description='Crawler Scheduler')
    parser.add_argument('--spider', '-s', help='Run specific spider')
    parser.add_argument('--all', '-a', action='store_true', help='Run all due spiders')
    parser.add_argument('--daemon', '-d', action='store_true', help='Run as daemon')
    parser.add_argument('--interval', type=int, default=60, help='Daemon check interval (seconds)')
    parser.add_argument('--database-url', help='Database URL')

    args = parser.parse_args()

    scheduler = CrawlerScheduler(args.database_url)

    if args.spider:
        scheduler.run_spider(args.spider)
    elif args.all:
        scheduler.run_all()
    elif args.daemon:
        scheduler.run_daemon(args.interval)
    else:
        parser.print_help()

    scheduler.close()


if __name__ == '__main__':
    main()
