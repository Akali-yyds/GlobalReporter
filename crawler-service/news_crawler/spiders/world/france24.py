"""
France24 Spider — uses France24 RSS feeds (English + French).
Covers world news, Europe, Middle East, Africa, Asia-Pacific.
"""
import logging
from datetime import datetime
from typing import Iterator

from scrapy import Request

from news_crawler.items import NewsArticle
from news_crawler.spiders.base import BaseNewsSpider

logger = logging.getLogger(__name__)

RSS_URLS = [
    ("https://www.france24.com/en/rss", "en", "GB"),
    ("https://www.france24.com/fr/rss", "fr", "FR"),
]


class France24Spider(BaseNewsSpider):

    name = "france24"
    source_name = "France 24"
    source_code = "france24"
    source_url = "https://www.france24.com"
    country = "FR"
    language = "en"
    category = "news"

    custom_settings = {
        **BaseNewsSpider.custom_settings,
        "DOWNLOAD_DELAY": 1.5,
        # Disable compression so decompressed body is directly parseable
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy.downloadermiddlewares.httpcompression.HttpCompressionMiddleware": None,
        },
    }

    def start_requests(self) -> Iterator[Request]:
        for url, lang, _ in RSS_URLS:
            yield Request(
                url=url,
                callback=self.parse_rss,
                dont_filter=True,
                meta={"lang": lang},
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"
                    ),
                    "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
                    "Accept-Encoding": "identity",
                },
            )

    def parse_rss(self, response, **kwargs) -> Iterator[NewsArticle]:
        lang = response.meta.get("lang", "en")
        items = response.xpath("//item")
        if not items:
            # Try alternate paths used by france24
            items = response.xpath("//entry")
        if not items:
            logger.warning(
                "France24: no items from %s. Status=%s body[:500]=%s",
                response.url,
                response.status,
                response.text[:500],
            )
            return

        for it in items:
            if len(self.crawled_items) >= self.max_items:
                break

            title = (it.xpath("string(title)").get() or "").strip()
            link = (
                it.xpath("link/text()").get() or
                it.xpath("link").get() or
                it.xpath("guid/text()").get() or
                ""
            ).strip()
            if not title or not link:
                continue

            if link in self.crawled_items:
                continue

            desc = (it.xpath("string(description)").get() or "").strip()
            pub = (it.xpath("pubDate/text()").get() or "").strip()
            cat = (it.xpath("category/text()").get() or "").strip()

            item = NewsArticle()
            item["title"] = self.clean_text(title)
            item["summary"] = self.clean_text(desc)
            item["url"] = link
            item["source_name"] = self.source_name
            item["source_code"] = self.source_code
            item["source_url"] = self.source_url
            item["published_at"] = pub or None
            item["crawled_at"] = datetime.now().isoformat()
            item["language"] = lang
            item["country"] = self.country
            item["category"] = cat or self.category
            item["heat_score"] = max(1, self.max_items - len(self.crawled_items))
            item["hash"] = self.compute_hash(title, self.source_code, link)
            self.crawled_items.append(item)
            yield item
