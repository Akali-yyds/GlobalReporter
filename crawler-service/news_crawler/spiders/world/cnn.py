"""
CNN Spider — HTML page parser.
CNN moved away from static SSR; headlines live in a JS-hydrated JSON blob inside
__NEXT_DATA__ or as plain text in the page. We use multiple CSS/XPath strategies.
"""
import logging
import re
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

        for link_sel in response.css("a[href]"):
            if count >= self.max_items:
                break

            raw_href = (link_sel.attrib.get("href") or "").strip()
            if not raw_href:
                continue

            url = response.urljoin(raw_href)
            if not self._is_article_url(url) or url in seen:
                continue

            title = self.clean_text(link_sel.xpath("normalize-space(string())").get())
            if not title or not self._looks_like_title(title):
                continue

            seen.add(url)
            count += 1
            item = self._make_item(url, title)
            self.crawled_items.append(item)
            yield item

        if count == 0:
            logger.warning(
                "CNN: no articles found. URL=%s Body snippet: %s",
                response.url,
                response.text[:600],
            )

    @staticmethod
    def _is_article_url(url: str) -> bool:
        if "cnn.com" not in url:
            return False
        if not re.search(r"/20\d{2}/\d{2}/\d{2}/", url):
            return False
        if "/video/" in url or "/videos/" in url:
            return False
        return True

    @staticmethod
    def _looks_like_title(title: str) -> bool:
        lower = title.lower()
        if len(title) < 12:
            return False
        if lower.startswith("video "):
            return False
        if "file photo" in lower or "getty images" in lower or lower.strip() == "reuters":
            return False
        return True

    def _make_item(self, url: str, title: str) -> NewsArticle:
        item = NewsArticle()
        item["title"] = title
        item["url"] = url
        item["source_name"] = self.source_name
        item["source_code"] = self.source_code
        item["source_url"] = self.source_url
        item["crawled_at"] = datetime.now().isoformat()
        item["language"] = self.language
        item["country"] = self.country
        item["category"] = self.category
        item["hash"] = self.compute_hash(title, url, self.source_code)
        return item
