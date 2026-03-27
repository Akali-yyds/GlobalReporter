#!/usr/bin/env python3
"""
Health check script for GlobalReporter services.
Can be used for monitoring and alerting.
"""
import sys
import time
import argparse
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()
import os

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://ainewser:ainewser_pass@localhost:5432/ainewser')
API_URL = os.getenv('API_URL', 'http://localhost:8000')


class HealthChecker:
    """Health check for all services."""

    def __init__(self, database_url: str = DATABASE_URL, api_url: str = API_URL):
        self.database_url = database_url
        self.api_url = api_url

    def check_database(self) -> Tuple[bool, str]:
        """Check database connectivity."""
        try:
            conn = psycopg2.connect(self.database_url)
            cur = conn.cursor()
            cur.execute('SELECT 1')
            cur.close()
            conn.close()
            return True, "Database connection OK"
        except Exception as e:
            return False, f"Database error: {e}"

    def check_api(self) -> Tuple[bool, str]:
        """Check API health endpoint."""
        try:
            response = requests.get(f'{self.api_url}/health', timeout=5)
            if response.status_code == 200:
                return True, f"API OK (response time: {response.elapsed.total_seconds()*1000:.0f}ms)"
            else:
                return False, f"API returned status {response.status_code}"
        except requests.exceptions.Timeout:
            return False, "API timeout"
        except Exception as e:
            return False, f"API error: {e}"

    def check_crawl_jobs(self, hours: int = 24) -> Tuple[bool, str]:
        """Check if crawl jobs are running successfully."""
        try:
            conn = psycopg2.connect(self.database_url)
            cur = conn.cursor(cursor_factory=RealDictCursor)

            # Check jobs in last N hours
            since = datetime.now() - timedelta(hours=hours)
            cur.execute(
                """
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
                FROM crawl_jobs
                WHERE started_at >= %s
                """,
                (since,)
            )
            result = cur.fetchone()
            cur.close()
            conn.close()

            if result:
                total = result['total'] or 0
                completed = result['completed'] or 0
                failed = result['failed'] or 0

                if total == 0:
                    return False, f"No crawl jobs in last {hours}h"
                if failed > completed:
                    return False, f"High failure rate: {failed}/{total} failed"
                
                return True, f"Jobs OK: {completed}/{total} completed, {failed} failed"
            
            return False, "No crawl job data"
        except Exception as e:
            return False, f"Crawl job check error: {e}"

    def check_data_freshness(self, max_age_hours: int = 2) -> Tuple[bool, str]:
        """Check if news data is fresh."""
        try:
            conn = psycopg2.connect(self.database_url)
            cur = conn.cursor()

            # Get the most recent article
            cur.execute(
                "SELECT MAX(crawl_time) as latest FROM news_articles"
            )
            result = cur.fetchone()
            cur.close()
            conn.close()

            if result and result[0]:
                latest = result[0]
                age = datetime.now() - latest
                age_hours = age.total_seconds() / 3600

                if age_hours > max_age_hours:
                    return False, f"Data stale: last update {age_hours:.1f}h ago"
                
                return True, f"Data fresh: last update {age.minutes}m ago"
            
            return False, "No articles in database"
        except Exception as e:
            return False, f"Freshness check error: {e}"

    def run_all_checks(self) -> Dict[str, Tuple[bool, str]]:
        """Run all health checks."""
        checks = {
            'database': self.check_database(),
            'api': self.check_api(),
            'crawl_jobs': self.check_crawl_jobs(),
            'data_freshness': self.check_data_freshness(),
        }
        return checks

    def print_report(self):
        """Print health check report."""
        checks = self.run_all_checks()
        
        print("\n" + "=" * 60)
        print("GlobalReporter Health Check Report")
        print(f"Timestamp: {datetime.now().isoformat()}")
        print("=" * 60)

        all_ok = True
        for name, (status, message) in checks.items():
            icon = "✓" if status else "✗"
            status_str = "OK" if status else "FAIL"
            print(f"[{icon}] {name:20} {status_str:6} - {message}")
            if not status:
                all_ok = False

        print("=" * 60)
        
        if all_ok:
            print("Status: HEALTHY")
            return 0
        else:
            print("Status: UNHEALTHY")
            return 1


def main():
    parser = argparse.ArgumentParser(description='GlobalReporter Health Check')
    parser.add_argument('--db', help='Database URL')
    parser.add_argument('--api', help='API URL')
    parser.add_argument('--watch', '-w', action='store_true', help='Watch mode (continuous)')
    parser.add_argument('--interval', type=int, default=60, help='Watch interval (seconds)')

    args = parser.parse_args()

    checker = HealthChecker(args.db or DATABASE_URL, args.api or API_URL)

    if args.watch:
        print(f"Watching health status (interval: {args.interval}s)")
        try:
            while True:
                exit_code = checker.print_report()
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nStopped.")
    else:
        exit_code = checker.print_report()
        sys.exit(exit_code if exit_code else 0)


if __name__ == '__main__':
    main()
