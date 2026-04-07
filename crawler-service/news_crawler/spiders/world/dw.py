"""
Deutsche Welle (DW) Spider — uses DW RSS feeds.
Covers world news, Europe, Germany from German international broadcaster.
"""
import logging
from datetime import datetime
from typing import Iterator

from scrapy import Request

from news_crawler.items import NewsArticle
from news_crawler.spiders.base import BaseNewsSpider

logger = logging.getLogger(__name__)

RSS_URLS = [
    ("https://rss.dw.com/rdf/rss-en-all", "en"),
    ("https://rss.dw.com/rdf/rss-en-world", "en"),
]


class DWSpider(BaseNewsSpider):

    name = "dw"
    source_name = "Deutsche Welle"
    source_code = "dw"
    source_url = "https://www.dw.com"
    country = "DE"
    language = "en"
    category = "news"

    custom_settings = {
        **BaseNewsSpider.custom_settings,
        "DOWNLOAD_DELAY": 1.5,
    }

    def start_requests(self) -> Iterator[Request]:
        for url, lang in RSS_URLS:
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
                    "Accept": "application/rss+xml, application/xml, text/xml, */*",
                },
            )

    def parse_rss(self, response, **kwargs) -> Iterator[NewsArticle]:
        lang = response.meta.get("lang", "en")
        # DW uses RSS 1.0 (RDF) format; must use local-name() to bypass namespace
        items = response.xpath("//*[local-name()='item']")
        if not items:
            logger.warning(
                "DW: no items from %s. Status=%s body[:300]=%s",
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
                or it.xpath("@*[local-name()='about']").get()
                or ""
            ).strip()
            if not title or not link:
                continue

            desc = (it.xpath("string(*[local-name()='description'])").get() or "").strip()
            pub = (
                it.xpath("*[local-name()='date']/text()").get()
                or it.xpath("pubDate/text()").get()
                or ""
            ).strip()
            cat = (it.xpath("*[local-name()='subject']/text()").get() or "").strip()

            item = NewsArticle()
            item["title"] = self.clean_text(title)
            item["summary"] = self.clean_text(desc)
            item["url"] = link
            item["source_name"] = self.source_name
            item["source_code"] = self.source_code
            item["source_url"] = self.source_url
            item["source_class"] = "news"
            item["source_tier"] = "authoritative"
            item["source_tier_level"] = 2
            item["freshness_sla_hours"] = 24
            item["license_mode"] = "publisher_public"
            item["published_at"] = pub or None
            item["crawled_at"] = datetime.now().isoformat()
            item["language"] = lang
            item["country"] = self.country
            item["category"] = cat or self.category
            item["canonical_url"] = link
            item["source_metadata"] = {
                "fetch_via": "official_rss",
                "feed_url": response.url,
            }
            item["heat_score"] = max(1, self.max_items - len(self.crawled_items))
            item["hash"] = self.compute_hash(title, self.source_code, link)
            self.crawled_items.append(item)
            yield item
