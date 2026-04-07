"""
Reuters spider.

Uses a Google News RSS site-search fallback because Reuters' public feed and site
are heavily bot-protected on the current network path. This keeps the spider
feed-first and avoids brittle HTML parsing while still surfacing Reuters links.
"""
from datetime import datetime
from typing import Iterator

from scrapy import Request

from news_crawler.items import NewsArticle
from news_crawler.spiders.base import BaseNewsSpider


class ReutersSpider(BaseNewsSpider):
    name = "reuters"
    source_name = "Reuters"
    source_code = "reuters"
    source_url = "https://www.reuters.com/"
    country = "US"
    language = "en"
    category = "news"

    RSS_URL = (
        "https://news.google.com/rss/search?"
        "q=site:reuters.com+when:1d&hl=en-US&gl=US&ceid=US:en"
    )

    custom_settings = {
        **BaseNewsSpider.custom_settings,
        "DOWNLOAD_DELAY": 1,
    }

    def start_requests(self) -> Iterator[Request]:
        yield Request(
            url=self.RSS_URL,
            callback=self.parse_feed,
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

    def parse_feed(self, response, **kwargs) -> Iterator[NewsArticle]:
        seen_links: set[str] = set()
        for it in response.xpath("//item"):
            if len(self.crawled_items) >= self.max_items:
                break

            title = self._clean_title((it.xpath("string(title)").get() or "").strip())
            link = (it.xpath("link/text()").get() or it.xpath("guid/text()").get() or "").strip()
            if not title or not link or link in seen_links:
                continue

            seen_links.add(link)
            item = NewsArticle()
            item["title"] = title
            item["summary"] = self.clean_text((it.xpath("string(description)").get() or "").strip())
            item["url"] = link
            item["canonical_url"] = link
            item["published_at"] = (it.xpath("pubDate/text()").get() or "").strip() or None
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
                "fetch_via": "google_news_rss_fallback",
                "publisher_domain": "reuters.com",
                "publisher_name": "Reuters",
            }
            item["heat_score"] = max(1, self.max_items - len(self.crawled_items))
            item["hash"] = self.compute_hash(title, self.source_code, link)
            self.crawled_items.append(item)
            yield item

    @staticmethod
    def _clean_title(value: str) -> str:
        if value.endswith(" - Reuters"):
            value = value[:-10]
        return value.strip()
