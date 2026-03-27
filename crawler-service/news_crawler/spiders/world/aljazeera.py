"""
Al Jazeera English Spider — uses Al Jazeera RSS feed.
Covers Middle East, Africa, Asia, world news from a non-Western perspective.
"""
import logging
from datetime import datetime
from typing import Iterator

from scrapy import Request

from news_crawler.items import NewsArticle
from news_crawler.spiders.base import BaseNewsSpider

logger = logging.getLogger(__name__)

RSS_URLS = [
    "https://www.aljazeera.com/xml/rss/all.xml",
]


class AlJazeeraSpider(BaseNewsSpider):

    name = "aljazeera"
    source_name = "Al Jazeera"
    source_code = "aljazeera"
    source_url = "https://www.aljazeera.com"
    country = "QA"
    language = "en"
    category = "news"

    custom_settings = {
        **BaseNewsSpider.custom_settings,
        "DOWNLOAD_DELAY": 1.5,
    }

    def start_requests(self) -> Iterator[Request]:
        for url in RSS_URLS:
            yield Request(
                url=url,
                callback=self.parse_rss,
                dont_filter=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"
                    ),
                    "Accept": "application/rss+xml, application/xml, text/xml, */*",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )

    def parse_rss(self, response, **kwargs) -> Iterator[NewsArticle]:
        items = response.xpath("//item")
        if not items:
            logger.warning(
                "AlJazeera: no items from %s. Status=%s body[:300]=%s",
                response.url,
                response.status,
                response.text[:300],
            )
            return

        for it in items:
            if len(self.crawled_items) >= self.max_items:
                break

            title = (it.xpath("string(title)").get() or "").strip()
            link = (
                it.xpath("link/text()").get()
                or it.xpath("link").get()
                or it.xpath("guid/text()").get()
                or ""
            ).strip()
            if not title or not link:
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
            item["language"] = self.language
            item["country"] = self.country
            item["category"] = cat or self.category
            item["heat_score"] = max(1, self.max_items - len(self.crawled_items))
            item["hash"] = self.compute_hash(title, self.source_code, link)
            self.crawled_items.append(item)
            yield item
