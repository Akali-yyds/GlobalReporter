"""
The Straits Times spider.

Uses official section RSS feeds for world and Asia coverage.
"""
from datetime import datetime
from typing import Iterator

from scrapy import Request

from news_crawler.items import NewsArticle
from news_crawler.spiders.base import BaseNewsSpider


RSS_URLS = [
    "https://www.straitstimes.com/news/world/rss.xml",
    "https://www.straitstimes.com/news/asia/rss.xml",
]


class StraitsTimesSpider(BaseNewsSpider):
    name = "straits_times"
    source_name = "The Straits Times"
    source_code = "straits_times"
    source_url = "https://www.straitstimes.com/"
    country = "SG"
    language = "en"
    category = "news"

    custom_settings = {
        **BaseNewsSpider.custom_settings,
        "DOWNLOAD_DELAY": 1.5,
        "DOWNLOADER_MIDDLEWARES": {
            "scrapy.downloadermiddlewares.httpcompression.HttpCompressionMiddleware": None,
        },
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
                    "Accept-Language": "en-SG,en;q=0.9",
                    "Accept-Encoding": "identity",
                },
            )

    def parse_rss(self, response, **kwargs) -> Iterator[NewsArticle]:
        items = response.xpath("//*[local-name()='item']")
        if not items:
            self.logger.warning(
                "StraitsTimes: no items from %s. Status=%s body[:300]=%s",
                response.url,
                response.status,
                response.text[:300],
            )
            return

        for it in items:
            if len(self.crawled_items) >= self.max_items:
                break

            title = (it.xpath("string(*[local-name()='title'])").get() or "").strip()
            link = (
                it.xpath("string(*[local-name()='link'])").get()
                or it.xpath("string(*[local-name()='guid'])").get()
                or ""
            ).strip()
            if not title or not link:
                continue

            item = NewsArticle()
            item["title"] = self.clean_text(title)
            item["summary"] = self.clean_text((it.xpath("string(*[local-name()='description'])").get() or "").strip())
            item["url"] = link
            item["canonical_url"] = link
            item["published_at"] = (it.xpath("string(*[local-name()='pubDate'])").get() or "").strip() or None
            item["source_name"] = self.source_name
            item["source_code"] = self.source_code
            item["source_url"] = self.source_url
            item["source_class"] = "news"
            item["source_tier"] = "authoritative"
            item["source_tier_level"] = 2
            item["freshness_sla_hours"] = 24
            item["license_mode"] = "publisher_public"
            item["crawled_at"] = datetime.now().isoformat()
            item["language"] = self.language
            item["country"] = self.country
            item["category"] = self.category
            item["source_metadata"] = {
                "fetch_via": "official_rss",
                "feed_url": response.url,
            }
            item["heat_score"] = max(1, self.max_items - len(self.crawled_items))
            item["hash"] = self.compute_hash(title, self.source_code, link)
            self.crawled_items.append(item)
            yield item
