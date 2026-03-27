"""
Scrapy settings for the news_crawler project.

This module contains all Scrapy settings for the news crawler.
Settings can be configured via environment variables or directly here.
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    _repo_env = Path(__file__).resolve().parent.parent.parent / ".env"
    if _repo_env.is_file():
        load_dotenv(_repo_env)
except Exception:
    pass

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Scrapy will seek for settings in this module path
BOT_NAME = "news_crawler"

# The __init__.py files are required for the module to be a package
SPIDER_MODULES = ["news_crawler.spiders"]
NEWSPIDER_MODULE = "news_crawler.spiders"

# Crawl responsibly (disabled for development)
ROBOTSTXT_OBEY = False

# Allow 401 responses so Reuters (which bot-blocks Scrapy) pages can still be parsed
HTTPCACHE_ENABLED = False

# Configure maximum concurrent requests performed by Scrapy
CONCURRENT_REQUESTS_PER_DOMAIN = 2

# Configure a delay for requests for the same website only
DOWNLOAD_DELAY = 1
RANDOMIZE_DOWNLOAD_DELAY = True

# Disable cookies (enabled by default)
COOKIES_ENABLED = True

# Override the default request headers
DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

# Custom middlewares disabled by default — they caused startup failures on some Windows setups.
SPIDER_MIDDLEWARES = {}

DOWNLOADER_MIDDLEWARES = {}

# Scrapy 2.11+ — silence deprecation
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"

# Enable or disable extensions
EXTENSIONS = {
    "scrapy.extensions.telnet.TelnetConsole": None,
}

# Configure item pipelines (ingest must run last)
ITEM_PIPELINES = {
    "news_crawler.pipelines.NewsCrawlerPipeline": 300,
    "news_crawler.pipelines.DeduplicationPipeline": 400,
    "news_crawler.pipelines.GeoExtractionPipeline": 450,
    "news_crawler.pipelines.ApiIngestPipeline": 500,
}

# Enable and configure the AutoThrottle extension
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0
AUTOTHROTTLE_DEBUG = False

# Allow 401 and 403 responses so bot-blocked sites (Reuters, RFI) can still parse response body
HTTPCERROR_ALLOWED_CODES = [401, 403]

# Enable and configure HTTP caching
HTTPCACHE_ENABLED = False

# Log settings
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
LOG_DATEFORMAT = "%Y-%m-%d %H:%M:%S"

# Close spider after certain number of items (useful for testing)
CLOSESPIDER_ITEMCOUNT = 100

# Close spider after certain time (in seconds)
# CLOSESPIDER_TIMEOUT = 3600

# Close spider after certain number of errors
CLOSESPIDER_ERRORCOUNT = 10

# Retry settings
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# Telnet settings
TELNETCONSOLE_ENABLED = False

# Optional settings for Playwright (if using scrapy-playwright)
# PLAYWRIGHT_ENABLED = False
# PLAYWRIGHT_BROWSER_TYPE = "chromium"
# PLAYWRIGHT_HEADLESS = True
# PLAYWRIGHT_LANGUAGE = "zh-CN"

# Database connection for pipeline (loaded from environment)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:123321@localhost:5432/ainewser?client_encoding=UTF8"
)

# Base URL of FastAPI (no trailing slash). Crawler POSTs to {API_BASE_URL}/api/news/ingest
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
