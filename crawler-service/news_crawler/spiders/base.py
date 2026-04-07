"""
Base Spider for all news crawlers.
Provides common functionality and structure.
"""
import re
import hashlib
import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional, Dict, Any, List

from scrapy import Spider, Request, Item, signals
from scrapy.http import Response
from itemloaders import ItemLoader

logger = logging.getLogger(__name__)


class BaseNewsSpider(Spider):
    """
    Base class for all news spiders.
    Provides common parsing utilities and data cleaning.
    """
    
    # Spider metadata - should be overridden by subclasses
    name: str = "base_news"
    source_name: str = "Unknown"
    source_code: str = "unknown"
    source_url: str = ""
    country: str = "CN"
    language: str = "zh"
    category: str = "news"
    
    # Crawling configuration
    max_items: int = 10  # Max items per crawl
    use_playwright: bool = False  # Override for dynamic pages
    
    custom_settings = {
        "DOWNLOAD_DELAY": 1,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 1,
        "AUTOTHROTTLE_MAX_DELAY": 10,
    }
    
    def __init__(self, *args, **kwargs):
        # Scrapy CLI: scrapy crawl spider -a max_items=80
        max_items_raw = kwargs.pop("max_items", None)
        self.feed_scope = str(kwargs.pop("feed_scope", "default") or "default").strip().lower()
        super().__init__(*args, **kwargs)
        if max_items_raw is not None:
            try:
                self.max_items = max(1, min(2000, int(max_items_raw)))
            except (TypeError, ValueError):
                pass
        self.crawled_items: List[Item] = []
        self.start_time: Optional[datetime] = None
        self._feed_runtime = {}
        self._feed_configs_by_url = {}
        self._feed_configs_by_code = {}

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)

        def _opened(_spider):
            _spider.start_time = datetime.now()

        crawler.signals.connect(_opened, signal=signals.spider_opened)
        return spider
    
    def start_requests(self):
        """Generate initial requests. Override in subclass."""
        raise NotImplementedError("Subclasses must implement start_requests()")
    
    def parse(self, response: Response, **kwargs):
        """Default parse method. Should be overridden."""
        raise NotImplementedError("Subclasses must implement parse()")
    
    def clean_text(self, text: Optional[str]) -> Optional[str]:
        """
        Clean extracted text:
        - Remove HTML tags
        - Remove extra whitespace
        - Strip leading/trailing spaces
        """
        if not text:
            return None
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Strip and return
        return text.strip() or None
    
    def clean_html(self, html: Optional[str]) -> Optional[str]:
        """Remove HTML but preserve basic structure."""
        if not html:
            return None
        
        # Remove script and style tags with content
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove HTML comments
        html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
        
        return html.strip() or None
    
    def parse_datetime(self, date_str: Optional[str]) -> Optional[datetime]:
        """
        Parse various datetime formats commonly found in RSS feeds and APIs.
        Always returns a naive UTC datetime or None.
        """
        if not date_str:
            return None

        date_str = self.clean_text(date_str)
        if not date_str:
            return None

        # RFC 2822 — most RSS feeds: "Tue, 25 Mar 2026 08:00:00 +0800"
        try:
            dt = parsedate_to_datetime(date_str)
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        except Exception:
            pass

        # ISO 8601 with or without timezone: "2026-03-25T08:00:00+08:00" / "Z"
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except ValueError:
            pass

        # Common plain formats (no timezone)
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
                    "%Y/%m/%d %H:%M:%S", "%Y/%m/%d",
                    "%m/%d/%Y %H:%M:%S", "%m/%d/%Y",
                    "%d/%m/%Y %H:%M:%S", "%d/%m/%Y"):
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        # Last resort: extract YYYY-MM-DD or YYYY/MM/DD fragment
        for pattern, fmt in (
            (r'\d{4}-\d{1,2}-\d{1,2}', '%Y-%m-%d'),
            (r'\d{4}/\d{1,2}/\d{1,2}', '%Y/%m/%d'),
        ):
            m = re.search(pattern, date_str)
            if m:
                try:
                    return datetime.strptime(m.group(0), fmt)
                except ValueError:
                    continue

        logger.warning("Could not parse date: %s", date_str)
        return None
    
    def compute_hash(self, *args) -> str:
        """
        Compute SHA256 hash from given strings.
        Used for deduplication.
        """
        content = '|'.join(str(arg) for arg in args if arg)
        return hashlib.sha256(content.encode()).hexdigest()
    
    def normalize_source_name(self, name: str) -> str:
        """Normalize source name to standard format."""
        name = self.clean_text(name) or ""
        
        # Map common variations to standard names
        name_map = {
            "新浪": "新浪新闻",
            "新浪网": "新浪新闻",
            "腾讯": "腾讯新闻",
            "腾讯网": "腾讯新闻",
            "网易": "网易新闻",
            "搜狐": "搜狐新闻",
            "微博": "微博热搜",
            "知乎": "知乎热榜",
            "BBC": "BBC News",
            "CNN": "CNN",
            "Reuters": "Reuters",
            "Twitter": "Twitter",
        }
        
        return name_map.get(name, name)
    
    def extract_article_url(self, url: str, base_url: str = "") -> str:
        """Extract and normalize article URL."""
        if not url:
            return ""
        
        # Handle relative URLs
        if url.startswith('/'):
            if base_url:
                from urllib.parse import urljoin
                return urljoin(base_url, url)
            return ""
        
        # Validate URL
        if not url.startswith(('http://', 'https://')):
            return ""
        
        return url
    
    def get_item_loader(self, item_class: type, response: Response) -> ItemLoader:
        """Create and return an ItemLoader instance."""
        return ItemLoader(item=item_class(), response=response)
    
    def closed(self, reason: str):
        """Called when spider is closed."""
        try:
            from news_crawler.utils.feed_control import flush_feed_health

            flush_feed_health(self)
        except Exception:
            logger.debug("Failed to flush feed health for %s", self.name, exc_info=True)
        elapsed = ""
        if self.start_time is not None:
            elapsed = f"{(datetime.now() - self.start_time).total_seconds():.2f}s"
        logger.info(
            "Spider %s closed: %s. Crawled %s items in %s",
            self.name,
            reason,
            len(self.crawled_items),
            elapsed or "n/a",
        )

    def get_controlled_feeds(self, fallback_feeds: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        from news_crawler.utils.feed_control import initialize_feed_runtime, resolve_feed_profiles

        feeds = resolve_feed_profiles(
            self.source_code,
            list(fallback_feeds or []),
            feed_scope=self.feed_scope,
        )
        initialize_feed_runtime(self, feeds)
        return feeds

    def get_response_feed(self, response: Response, fallback_feeds: List[Dict[str, Any]]) -> Dict[str, Any]:
        from news_crawler.utils.feed_control import feed_for_response

        return feed_for_response(self, response, list(fallback_feeds or []))

    def handle_feed_error(self, failure) -> None:
        from news_crawler.utils.feed_control import record_feed_fetch

        request = getattr(failure, "request", None)
        meta = getattr(request, "meta", {}) if request else {}
        response = getattr(getattr(failure, "value", None), "response", None)
        feed_code = str(meta.get("feed_code") or meta.get("feed_name") or "default").strip()
        feed_name = str(meta.get("feed_name") or feed_code).strip()
        feed_url = getattr(request, "url", None)
        http_status = getattr(response, "status", None)
        error_text = str(getattr(failure, "value", failure))
        record_feed_fetch(
            self,
            feed_code=feed_code,
            feed_name=feed_name,
            feed_url=feed_url,
            http_status=http_status,
            success=False,
            error=error_text[:500],
        )
        logger.warning("Feed request failed spider=%s feed=%s status=%s error=%s", self.name, feed_name, http_status, error_text[:300])


class NewsSpiderMixin:
    """
    Mixin class providing additional news-specific utilities.
    Use with BaseNewsSpider for full functionality.
    """
    
    def extract_summary(self, response: Response, selectors: List[str]) -> Optional[str]:
        """Extract summary/description from response using multiple selectors."""
        for selector in selectors:
            summary = response.css(selector).get() or response.xpath(selector).get()
            if summary:
                cleaned = self.clean_text(summary)
                if cleaned and len(cleaned) > 10:
                    return cleaned
        return None
    
    def extract_author(self, response: Response, selectors: List[str]) -> Optional[str]:
        """Extract author name from response."""
        for selector in selectors:
            author = response.css(selector).get() or response.xpath(selector).get()
            if author:
                cleaned = self.clean_text(author)
                if cleaned:
                    return cleaned
        return None
    
    def extract_category(self, response: Response, selectors: List[str]) -> Optional[str]:
        """Extract category from response."""
        for selector in selectors:
            category = response.css(selector).get() or response.xpath(selector).get()
            if category:
                cleaned = self.clean_text(category)
                if cleaned:
                    return cleaned
        return None
    
    def should_follow_url(self, url: str, allowed_patterns: List[str] = None) -> bool:
        """
        Check if URL should be followed based on patterns.
        If allowed_patterns is None, allow all URLs starting with http/https.
        """
        if not url:
            return False
        
        if not url.startswith(('http://', 'https://')):
            return False
        
        if allowed_patterns:
            return any(re.search(pattern, url) for pattern in allowed_patterns)
        
        return True
