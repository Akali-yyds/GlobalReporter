"""
Sina News (新浪新闻) Spider — multi-strategy.
Tries official RSS first, then falls back to multiple JSON APIs.
"""
import logging
from datetime import datetime
from typing import Iterator
from urllib.parse import urlencode

from scrapy import Request

from news_crawler.items import NewsArticle
from news_crawler.spiders.base import BaseNewsSpider

logger = logging.getLogger(__name__)

# Sina JSON roll API — pageid=153 (national hot news) is confirmed working
RSS_URLS = [
    "https://feed.mix.sina.com.cn/api/roll/get?" + urlencode({
        "pageid": 153, "lid": 2509, "num": 20, "page": 1,
    }),
    "https://feed.mix.sina.com.cn/api/roll/get?" + urlencode({
        "pageid": 153, "lid": 2510, "num": 20, "page": 1,
    }),
]


class SinaSpider(BaseNewsSpider):

    name = "sina"
    source_name = "新浪新闻"
    source_code = "sina"
    source_url = "https://news.sina.com.cn"
    country = "CN"
    language = "zh"
    category = "news"

    custom_settings = {
        **BaseNewsSpider.custom_settings,
        "DOWNLOAD_DELAY": 0.5,
    }

    def start_requests(self) -> Iterator[Request]:
        for url in RSS_URLS:
            yield Request(
                url=url,
                callback=self.parse,
                dont_filter=True,
                headers={
                    "Referer": "https://news.sina.com.cn/",
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"
                    ),
                    "Accept-Language": "zh-CN,zh;q=0.9",
                },
            )

    def parse(self, response, **kwargs) -> Iterator[NewsArticle]:
        url = response.url
        before = len(self.crawled_items)

        if url.endswith(".xml") or "rss.sina" in url:
            yield from self._parse_rss(response)
        elif "feed.mix.sina" in url or "api/roll" in url:
            yield from self._parse_json_api(response)

        if len(self.crawled_items) == before:
            logger.warning(
                "Sina: 0 items from %s. Status=%s body[:200]=%s",
                url,
                response.status,
                response.text[:200],
            )

    def _parse_rss(self, response) -> int:
        """Parse RSS 2.0 XML feed."""
        items = response.xpath("//item")
        if not items:
            items = response.xpath("//entry")
        count = 0
        seen: set[str] = set()

        for it in items:
            if count >= self.max_items:
                break
            title = (it.xpath("string(title)").get() or "").strip()
            link = (
                it.xpath("link/text()").get() or
                it.xpath("link").get() or
                it.xpath("@href").get() or
                ""
            ).strip()
            if not title or not link:
                continue
            if link in seen:
                continue
            seen.add(link)
            count += 1

            desc = (it.xpath("string(description)").get() or "").strip()
            pub = (it.xpath("pubDate/text()").get() or "").strip()

            item = NewsArticle()
            item["title"] = self.clean_text(title)
            item["summary"] = self.clean_text(desc)
            item["url"] = link
            item["source_name"] = self.source_name
            item["source_code"] = self.source_code
            item["source_url"] = self.source_url
            item["published_at"] = pub or None
            item["crawled_at"] = datetime.now().isoformat()
            item["language"] = self.language
            item["country"] = self.country
            item["category"] = self.category
            item["hash"] = self.compute_hash(title, self.source_code, link)
            self.crawled_items.append(item)
            yield item

        return count

    def _parse_json_api(self, response) -> int:
        """Parse the JSON API response from feed.mix.sina.com.cn."""
        try:
            import json
            data = json.loads(response.text)
        except Exception as e:
            logger.warning("Sina JSON parse error: %s", e)
            return 0

        # Handle {result: {data: [...]}}
        result = data.get("result") or {}
        items = result.get("data") or result.get("list") or data.get("data") or []
        count = 0
        seen: set[str] = set()

        for row in items:
            if count >= self.max_items:
                break
            title = (row.get("title") or "").strip()
            link = (row.get("url") or "").strip()
            if not title or not link:
                continue
            if link in seen:
                continue
            seen.add(link)
            count += 1

            item = NewsArticle()
            item["title"] = self.clean_text(title)
            item["summary"] = self.clean_text(row.get("intro") or row.get("html") or "")
            item["url"] = link
            item["source_name"] = self.source_name
            item["source_code"] = self.source_code
            item["source_url"] = self.source_url
            item["published_at"] = row.get("ctime") or None
            item["crawled_at"] = datetime.now().isoformat()
            item["language"] = self.language
            item["country"] = self.country
            item["category"] = row.get("type_cn") or self.category
            item["hash"] = self.compute_hash(title, self.source_code, link)
            self.crawled_items.append(item)
            yield item

        return count
