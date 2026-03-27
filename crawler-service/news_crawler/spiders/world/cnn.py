"""
CNN Spider — HTML page parser.
CNN moved away from static SSR; headlines live in a JS-hydrated JSON blob inside
__NEXT_DATA__ or as plain text in the page. We use multiple CSS/XPath strategies.
"""
import json
import logging
from datetime import datetime
from typing import Iterator

from scrapy import Request

from news_crawler.items import NewsArticle
from news_crawler.spiders.base import BaseNewsSpider

logger = logging.getLogger(__name__)


class CNNSpider(BaseNewsSpider):

    name = "cnn"
    source_name = "CNN"
    source_code = "cnn"
    source_url = "https://www.cnn.com"
    country = "US"
    language = "en"
    category = "news"

    START_URL = "https://www.cnn.com/"

    def start_requests(self) -> Iterator[Request]:
        yield Request(
            url=self.START_URL,
            callback=self.parse,
            dont_filter=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            },
        )

    def parse(self, response, **kwargs) -> Iterator[NewsArticle]:
        count = 0
        seen: set[str] = set()

        # Strategy 1: extract __NEXT_DATA__ JSON (contains full article list)
        try:
            raw = response.css('script[id="__NEXT_DATA__"]::text').get() or ""
            nd = json.loads(raw)
            # Walk the JSON for article URLs (typical CNN data structure)
            for url in self._extract_urls_from_json(nd):
                if count >= self.max_items:
                    break
                url = url.strip()
                if not url.startswith("http"):
                    url = "https://www.cnn.com" + url
                if url in seen or "cnn.com" not in url:
                    continue
                seen.add(url)
                count += 1
                self.crawled_items.append(self._make_item(url))
                yield self._make_item(url)
        except Exception as exc:
            logger.debug("CNN __NEXT_DATA__ parse failed: %s", exc)

        # Strategy 2: plain link extraction from HTML
        if count < self.max_items:
            raw_links = response.css(
                'a[href*="/202"]'
            ).xpath("@href").getall()  # 2024/2025/2026 date pattern

            for raw_url in raw_links:
                if count >= self.max_items:
                    break
                url = raw_url.strip()
                if not url.startswith("http"):
                    url = "https://www.cnn.com" + url
                if url in seen or "cnn.com/+" in url or "cnn.com/videos" in url:
                    continue
                seen.add(url)
                count += 1
                self.crawled_items.append(self._make_item(url))
                yield self._make_item(url)

        if count == 0:
            logger.warning(
                "CNN: no articles found. URL=%s Body snippet: %s",
                response.url,
                response.text[:600],
            )

    def _extract_urls_from_json(self, node) -> Iterator[str]:
        """Walk a parsed JSON object, yield URL strings."""
        if isinstance(node, dict):
            for v in node.values():
                yield from self._extract_urls_from_json(v)
        elif isinstance(node, list):
            for item in node:
                yield from self._extract_urls_from_json(item)
        elif isinstance(node, str):
            if ("cnn.com/202" in node or "/world/" in node or "/politics/" in node
                    or "/business/" in node) and len(node) < 200:
                yield node

    def _make_item(self, url: str) -> NewsArticle:
        item = NewsArticle()
        item["title"] = None
        item["url"] = url
        item["source_name"] = self.source_name
        item["source_code"] = self.source_code
        item["source_url"] = self.source_url
        item["crawled_at"] = datetime.now().isoformat()
        item["language"] = self.language
        item["country"] = self.country
        item["category"] = self.category
        item["hash"] = self.compute_hash(url, self.source_code)
        return item
